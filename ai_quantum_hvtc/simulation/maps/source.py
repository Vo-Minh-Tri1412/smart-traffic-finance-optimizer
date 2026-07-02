from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SumoMapSourceError(ValueError):
    """Raised when a SUMO map source descriptor or net file is invalid."""


@dataclass(frozen=True)
class SumoNetSource:
    net_path: Path
    source_id: str
    source_kind: str = "sumo_net_xml"
    expected_sha256: str = ""


@dataclass(frozen=True)
class SumoProjectDescriptor:
    project_id: str
    name: str
    version: str
    source: SumoNetSource
    overlay_path: Path
    demand_config_path: Path
    raw_dvc_path: Path | None = None
    prepared_dvc_path: Path | None = None
    import_profile: str = ""
    notes: str = ""
    descriptor_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SumoNetIndex:
    net_path: Path
    edge_ids: frozenset[str]
    lane_ids: frozenset[str]
    junction_ids: frozenset[str]
    traffic_light_ids: frozenset[str]
    lane_to_edge: dict[str, str]
    edge_to_lanes: dict[str, tuple[str, ...]]
    edge_shapes: dict[str, tuple[tuple[float, float], ...]]
    lane_shapes: dict[str, tuple[tuple[float, float], ...]]
    junction_points: dict[str, tuple[float, float]]
    junction_shapes: dict[str, tuple[tuple[float, float], ...]]
    bounds_min: tuple[float, float]
    bounds_max: tuple[float, float]

    @property
    def edge_count(self) -> int:
        return len(self.edge_ids)

    @property
    def lane_count(self) -> int:
        return len(self.lane_ids)

    @property
    def junction_count(self) -> int:
        return len(self.junction_ids)

    @property
    def traffic_light_count(self) -> int:
        return len(self.traffic_light_ids)

    def contains_edge(self, edge_id: str) -> bool:
        return edge_id in self.edge_ids

    def contains_lane(self, lane_id: str) -> bool:
        return lane_id in self.lane_ids

    def contains_junction(self, junction_id: str) -> bool:
        return junction_id in self.junction_ids

    def first_lane_for_edge(self, edge_id: str) -> str:
        lanes = self.edge_to_lanes.get(edge_id, ())
        return lanes[0] if lanes else ""


def load_sumo_project(path: Path | str) -> SumoProjectDescriptor:
    descriptor_path = Path(path).resolve()
    data = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SumoMapSourceError(f"{descriptor_path}: project descriptor must be a JSON object")
    base_dir = descriptor_path.parent
    source_data = _object(data, "source")
    source = SumoNetSource(
        net_path=_resolve(base_dir, str(source_data["net_path"])),
        source_id=str(source_data.get("id", data.get("id", "sumo_net_source"))),
        source_kind=str(source_data.get("kind", "sumo_net_xml")),
        expected_sha256=str(source_data.get("sha256", "")),
    )
    descriptor = SumoProjectDescriptor(
        project_id=str(data["id"]),
        name=str(data["name"]),
        version=str(data["version"]),
        source=source,
        overlay_path=_resolve(base_dir, str(data["semantic_overlay_path"])),
        demand_config_path=_resolve(base_dir, str(data["demand_config_path"])),
        raw_dvc_path=_resolve_optional(base_dir, data.get("raw_dvc_path")),
        prepared_dvc_path=_resolve_optional(base_dir, data.get("prepared_dvc_path")),
        import_profile=str(data.get("import_profile", "")),
        notes=str(data.get("notes", "")),
        descriptor_path=descriptor_path,
        raw=data,
    )
    validate_sumo_project_descriptor(descriptor)
    return descriptor


def validate_sumo_project_descriptor(descriptor: SumoProjectDescriptor) -> None:
    if not descriptor.source.net_path.is_file():
        raise SumoMapSourceError(f"SUMO net file not found: {descriptor.source.net_path}")
    if descriptor.source.expected_sha256:
        actual_sha = sha256_file(descriptor.source.net_path)
        if actual_sha != descriptor.source.expected_sha256:
            raise SumoMapSourceError(
                "SUMO net checksum mismatch: "
                f"expected {descriptor.source.expected_sha256}, got {actual_sha}"
            )
    if not descriptor.overlay_path.is_file():
        raise SumoMapSourceError(f"semantic overlay not found: {descriptor.overlay_path}")
    if not descriptor.demand_config_path.is_file():
        raise SumoMapSourceError(f"demand config not found: {descriptor.demand_config_path}")


def load_sumo_net_index(path: Path | str) -> SumoNetIndex:
    net_path = Path(path).resolve()
    if not net_path.is_file():
        raise SumoMapSourceError(f"SUMO net file not found: {net_path}")

    edge_ids: set[str] = set()
    lane_ids: set[str] = set()
    junction_ids: set[str] = set()
    traffic_light_ids: set[str] = set()
    lane_to_edge: dict[str, str] = {}
    edge_to_lanes_mut: dict[str, list[str]] = {}
    edge_shapes: dict[str, tuple[tuple[float, float], ...]] = {}
    lane_shapes: dict[str, tuple[tuple[float, float], ...]] = {}
    junction_points: dict[str, tuple[float, float]] = {}
    junction_shapes: dict[str, tuple[tuple[float, float], ...]] = {}
    bounds: list[tuple[float, float]] = []

    current_edge_id = ""
    current_edge_internal = False
    for event, element in ET.iterparse(net_path, events=("start", "end")):
        tag = _strip_namespace(element.tag)
        if event == "start" and tag == "edge":
            current_edge_id = str(element.attrib.get("id", ""))
            current_edge_internal = current_edge_id.startswith(":") or (
                element.attrib.get("function") == "internal"
            )
            if current_edge_id and not current_edge_internal:
                edge_ids.add(current_edge_id)
                edge_to_lanes_mut.setdefault(current_edge_id, [])
                edge_shape = _parse_shape(element.attrib.get("shape", ""))
                if edge_shape:
                    edge_shapes[current_edge_id] = edge_shape
                    bounds.extend(edge_shape)
        elif event == "start" and tag == "lane":
            lane_id = str(element.attrib.get("id", ""))
            if current_edge_id and lane_id and not current_edge_internal:
                lane_ids.add(lane_id)
                lane_to_edge[lane_id] = current_edge_id
                edge_to_lanes_mut.setdefault(current_edge_id, []).append(lane_id)
                lane_shape = _parse_shape(element.attrib.get("shape", ""))
                if lane_shape:
                    lane_shapes[lane_id] = lane_shape
                    if current_edge_id not in edge_shapes:
                        edge_shapes[current_edge_id] = lane_shape
                    bounds.extend(lane_shape)
        elif event == "start" and tag == "junction":
            junction_id = str(element.attrib.get("id", ""))
            if junction_id and not junction_id.startswith(":"):
                junction_ids.add(junction_id)
                if element.attrib.get("type") == "traffic_light":
                    traffic_light_ids.add(junction_id)
                if "x" in element.attrib and "y" in element.attrib:
                    point = (float(element.attrib["x"]), float(element.attrib["y"]))
                    junction_points[junction_id] = point
                    bounds.append(point)
                shape = _parse_shape(element.attrib.get("shape", ""))
                if shape:
                    junction_shapes[junction_id] = shape
                    bounds.extend(shape)
        elif event == "end" and tag == "edge":
            current_edge_id = ""
            current_edge_internal = False
            element.clear()

    bounds_min, bounds_max = _bounds(bounds)
    return SumoNetIndex(
        net_path=net_path,
        edge_ids=frozenset(edge_ids),
        lane_ids=frozenset(lane_ids),
        junction_ids=frozenset(junction_ids),
        traffic_light_ids=frozenset(traffic_light_ids),
        lane_to_edge=lane_to_edge,
        edge_to_lanes={key: tuple(value) for key, value in edge_to_lanes_mut.items()},
        edge_shapes=edge_shapes,
        lane_shapes=lane_shapes,
        junction_points=junction_points,
        junction_shapes=junction_shapes,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _resolve_optional(base_dir: Path, value: object) -> Path | None:
    if value is None or str(value) == "":
        return None
    return _resolve(base_dir, str(value))


def _object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise SumoMapSourceError(f"{key} must be an object")
    return value


def _parse_shape(value: str) -> tuple[tuple[float, float], ...]:
    points = []
    for token in value.split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            points.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return tuple(points)


def _bounds(points: list[tuple[float, float]]) -> tuple[tuple[float, float], tuple[float, float]]:
    if not points:
        return (0.0, 0.0), (0.0, 0.0)
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return (min_x, min_y), (max_x, max_y)


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
