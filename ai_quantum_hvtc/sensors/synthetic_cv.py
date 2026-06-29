from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

YOLO_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
DEFAULT_SYNTHETIC_YOLO_CLASSES = (
    "motorbike",
    "car",
    "bus",
    "truck",
    "ambulance",
    "worker_shuttle",
    "taxi_ride_hailing",
    "delivery_bike",
)
REQUIRED_YOLO_SUBDIRS = (
    Path("images") / "train",
    Path("images") / "val",
    Path("labels") / "train",
    Path("labels") / "val",
)


@dataclass(frozen=True)
class SyntheticDatasetPaths:
    root: Path
    data_yaml: Path
    dataset_manifest: Path
    render_manifest: Path
    camera_config: Path


@dataclass(frozen=True)
class DatasetValidationResult:
    dataset_root: Path
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def expected_yolo_paths(dataset_root: Path) -> list[Path]:
    return [dataset_root / subdir for subdir in REQUIRED_YOLO_SUBDIRS]


def synthetic_dataset_paths(dataset_root: Path) -> SyntheticDatasetPaths:
    return SyntheticDatasetPaths(
        root=dataset_root,
        data_yaml=dataset_root / "data.yaml",
        dataset_manifest=dataset_root / "dataset_manifest.json",
        render_manifest=dataset_root / "render_manifest.json",
        camera_config=dataset_root / "camera_config.template.json",
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def data_yaml_text(class_names: tuple[str, ...]) -> str:
    lines = [
        "path: .",
        "train: images/train",
        "val: images/val",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(class_names))
    return "\n".join(lines) + "\n"


def init_synthetic_yolo_dataset(
    *,
    dataset_id: str,
    output_root: Path,
    class_names: tuple[str, ...] = DEFAULT_SYNTHETIC_YOLO_CLASSES,
    force: bool = False,
    render_id: str | None = None,
    source_run_id: str = "",
) -> SyntheticDatasetPaths:
    dataset_root = output_root / dataset_id
    if dataset_root.exists() and any(dataset_root.iterdir()) and not force:
        raise FileExistsError(
            f"Dataset folder already exists; use --force to replace: {dataset_root}"
        )

    for path in expected_yolo_paths(dataset_root):
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").write_text("", encoding="utf-8")

    paths = synthetic_dataset_paths(dataset_root)
    paths.data_yaml.write_text(data_yaml_text(class_names), encoding="utf-8")
    write_json(
        paths.dataset_manifest,
        {
            "dataset_id": dataset_id,
            "stream": "cv_yolo",
            "format": "ultralytics_yolo_detection",
            "source_type": "godot_synthetic_camera",
            "status": "template_only",
            "class_names": list(class_names),
            "notes": (
                "This is the project-specific synthetic visual-sensor dataset contract. "
                "Generated frames and labels should come from Godot-rendered SUMO/SUMO-RL traces."
            ),
        },
    )
    write_json(
        paths.render_manifest,
        {
            "render_id": render_id or f"RENDER-{dataset_id}",
            "dataset_id": dataset_id,
            "source_run_id": source_run_id,
            "source_engine": "sumo_sumo_rl",
            "renderer": "godot_3d",
            "label_format": "yolo_detection",
            "image_size": [640, 640],
            "weather_profiles": ["clear_day"],
            "lighting_profiles": ["day"],
            "camera_ids": [],
            "status": "template_only",
            "caveat": "No real frames are included until Godot render export is run.",
        },
    )
    write_json(
        paths.camera_config,
        {
            "version": "v0.1",
            "coordinate_system": "sumo_xy_to_godot_xz",
            "cameras": [
                {
                    "camera_id": "CAM_I06_HOSPITAL_GATE",
                    "intersection_id": "I06",
                    "purpose": "hospital emergency access visual sensor",
                    "position": {"x": 0.0, "y": 8.0, "z": 0.0},
                    "rotation_degrees": {"x": -25.0, "y": 0.0, "z": 0.0},
                    "fov_degrees": 60.0,
                }
            ],
        },
    )
    return paths


def validate_synthetic_yolo_dataset(dataset_root: Path) -> DatasetValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    paths = synthetic_dataset_paths(dataset_root)

    for path in expected_yolo_paths(dataset_root):
        if not path.is_dir():
            errors.append(f"Missing folder: {path}")

    if not paths.data_yaml.is_file():
        errors.append(f"Missing file: {paths.data_yaml}")
        class_count = 0
    else:
        class_count = _class_count_from_data_yaml(paths.data_yaml)
        if class_count <= 0:
            errors.append(f"No class names found in: {paths.data_yaml}")

    for manifest_path in (paths.dataset_manifest, paths.render_manifest, paths.camera_config):
        if not manifest_path.is_file():
            errors.append(f"Missing file: {manifest_path}")
        else:
            _validate_json_file(manifest_path, errors)

    for split in ("train", "val"):
        warnings.extend(
            _validate_split(
                dataset_root=dataset_root,
                split=split,
                class_count=class_count,
            )
        )

    return DatasetValidationResult(
        dataset_root=dataset_root,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _class_count_from_data_yaml(path: Path) -> int:
    count = 0
    in_names = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.strip() == "names:":
            in_names = True
            continue
        if in_names:
            if line.startswith("  ") and ":" in line:
                count += 1
            elif line.strip():
                break
    return count


def _validate_json_file(path: Path, errors: list[str]) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON {path}: {exc}")


def _validate_split(*, dataset_root: Path, split: str, class_count: int) -> list[str]:
    warnings: list[str] = []
    image_dir = dataset_root / "images" / split
    label_dir = dataset_root / "labels" / split
    if not image_dir.is_dir() or not label_dir.is_dir():
        return warnings

    image_stems = {
        path.stem
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in YOLO_IMAGE_EXTENSIONS
    }
    label_paths = [path for path in label_dir.glob("*.txt") if path.is_file()]
    label_stems = {path.stem for path in label_paths}

    if not image_stems and not label_stems:
        warnings.append(f"{split}: no images or labels yet; dataset is template/smoke only")
        return warnings

    for missing_label in sorted(image_stems - label_stems):
        warnings.append(f"{split}: image has no label file: {missing_label}")
    for missing_image in sorted(label_stems - image_stems):
        warnings.append(f"{split}: label has no matching image: {missing_image}")

    for label_path in label_paths:
        warnings.extend(_validate_label_file(label_path, class_count=class_count))
    return warnings


def _validate_label_file(path: Path, *, class_count: int) -> list[str]:
    warnings: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            warnings.append(f"{path}:{line_number}: expected 5 YOLO fields, got {len(parts)}")
            continue
        try:
            class_id = int(parts[0])
            values = [float(value) for value in parts[1:]]
        except ValueError:
            warnings.append(f"{path}:{line_number}: non-numeric YOLO label field")
            continue
        if class_id < 0 or class_id >= class_count:
            warnings.append(
                f"{path}:{line_number}: class_id {class_id} outside 0..{class_count - 1}"
            )
        if any(value < 0.0 or value > 1.0 for value in values):
            warnings.append(f"{path}:{line_number}: bbox values must be normalized to 0..1")
    return warnings
