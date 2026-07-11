"""Deterministic, headless geometry visibility for camera-partial observations.

The module intentionally consumes SUMO metres and canonical vehicle boxes.  It does not use
Godot meshes, player-camera LOD, RGB pixels, or a learned detector.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CAMERA_CALIBRATION_SCHEMA_VERSION = "camera_calibration.v1"
VISIBILITY_TRACE_SCHEMA_VERSION = "visibility_trace.v1"
SENSOR_OBSERVATION_SCHEMA_VERSION = "sensor_observation.v1"
_EPSILON = 1e-7

Vec3 = tuple[float, float, float]


class GeometryContractError(ValueError):
    """Raised when a trace or calibration cannot support physical visibility."""


@dataclass(frozen=True)
class CameraCalibration:
    camera_id: str
    position_m: Vec3
    yaw_degrees: float
    pitch_degrees: float
    image_width: int
    image_height: int
    fx: float
    fy: float
    cx: float
    cy: float
    near_clip_m: float = 0.1
    far_clip_m: float = 500.0
    capture_interval_seconds: float = 1.0
    target_lane_ids: tuple[str, ...] = ()
    role: str = "intersection"
    visibility_width: int | None = None
    visibility_height: int | None = None

    def __post_init__(self) -> None:
        if not self.camera_id:
            raise GeometryContractError("camera_id must not be empty")
        if self.image_width < 2 or self.image_height < 2:
            raise GeometryContractError("camera image dimensions must be at least 2 pixels")
        if self.fx <= 0 or self.fy <= 0:
            raise GeometryContractError("camera focal lengths must be positive")
        if self.near_clip_m <= 0 or self.far_clip_m <= self.near_clip_m:
            raise GeometryContractError("camera clipping planes are invalid")
        if self.capture_interval_seconds <= 0:
            raise GeometryContractError("camera capture interval must be positive")
        if self.visibility_width is not None and self.visibility_width < 2:
            raise GeometryContractError("geometry raster width must be at least 2 pixels")
        if self.visibility_height is not None and self.visibility_height < 2:
            raise GeometryContractError("geometry raster height must be at least 2 pixels")

    @classmethod
    def from_fov(
        cls,
        *,
        camera_id: str,
        position_m: Vec3,
        yaw_degrees: float,
        pitch_degrees: float,
        image_width: int,
        image_height: int,
        vertical_fov_degrees: float,
        near_clip_m: float = 0.1,
        far_clip_m: float = 500.0,
        capture_interval_seconds: float = 1.0,
        target_lane_ids: tuple[str, ...] = (),
        role: str = "intersection",
        visibility_width: int | None = None,
        visibility_height: int | None = None,
    ) -> CameraCalibration:
        if not 0 < vertical_fov_degrees < 179:
            raise GeometryContractError("vertical_fov_degrees must be between 0 and 179")
        fy = image_height / (2.0 * math.tan(math.radians(vertical_fov_degrees) / 2.0))
        return cls(
            camera_id=camera_id,
            position_m=position_m,
            yaw_degrees=yaw_degrees,
            pitch_degrees=pitch_degrees,
            image_width=image_width,
            image_height=image_height,
            fx=fy,
            fy=fy,
            cx=(image_width - 1) / 2.0,
            cy=(image_height - 1) / 2.0,
            near_clip_m=near_clip_m,
            far_clip_m=far_clip_m,
            capture_interval_seconds=capture_interval_seconds,
            target_lane_ids=target_lane_ids,
            role=role,
            visibility_width=visibility_width,
            visibility_height=visibility_height,
        )

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> CameraCalibration:
        schema_version = str(row.get("schema_version", CAMERA_CALIBRATION_SCHEMA_VERSION))
        if schema_version != CAMERA_CALIBRATION_SCHEMA_VERSION:
            raise GeometryContractError(
                f"Unsupported camera calibration schema_version={schema_version}"
            )
        position = _vec3(row.get("position_m"), "position_m")
        rotation = row.get("rotation_degrees", {})
        if not isinstance(rotation, dict):
            raise GeometryContractError("rotation_degrees must be an object")
        image = row.get("image_size", {})
        if not isinstance(image, dict):
            raise GeometryContractError("image_size must be an object")
        intrinsics = row.get("intrinsics", {})
        if not isinstance(intrinsics, dict):
            raise GeometryContractError("intrinsics must be an object")
        raster_size = row.get("geometry_raster_size", {})
        if not isinstance(raster_size, dict):
            raise GeometryContractError("geometry_raster_size must be an object")
        return cls(
            camera_id=str(row.get("camera_id", "")),
            position_m=position,
            yaw_degrees=float(rotation.get("yaw", 0.0)),
            pitch_degrees=float(rotation.get("pitch", 0.0)),
            image_width=int(image.get("width", 0)),
            image_height=int(image.get("height", 0)),
            fx=float(intrinsics.get("fx", 0.0)),
            fy=float(intrinsics.get("fy", 0.0)),
            cx=float(intrinsics.get("cx", 0.0)),
            cy=float(intrinsics.get("cy", 0.0)),
            near_clip_m=float(row.get("near_clip_m", 0.1)),
            far_clip_m=float(row.get("far_clip_m", 500.0)),
            capture_interval_seconds=float(row.get("capture_interval_seconds", 1.0)),
            target_lane_ids=tuple(str(value) for value in row.get("target_lane_ids", [])),
            role=str(row.get("role", "intersection")),
            visibility_width=(int(raster_size["width"]) if "width" in raster_size else None),
            visibility_height=(int(raster_size["height"]) if "height" in raster_size else None),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": CAMERA_CALIBRATION_SCHEMA_VERSION,
            "camera_id": self.camera_id,
            "coordinate_system": "sumo_xy_meters_z_up",
            "position_m": list(self.position_m),
            "rotation_degrees": {"yaw": self.yaw_degrees, "pitch": self.pitch_degrees},
            "image_size": {"width": self.image_width, "height": self.image_height},
            "intrinsics": {"fx": self.fx, "fy": self.fy, "cx": self.cx, "cy": self.cy},
            "near_clip_m": self.near_clip_m,
            "far_clip_m": self.far_clip_m,
            "capture_interval_seconds": self.capture_interval_seconds,
            "target_lane_ids": list(self.target_lane_ids),
            "role": self.role,
        }
        if self.visibility_width is not None or self.visibility_height is not None:
            payload["geometry_raster_size"] = {
                "width": self.raster_width,
                "height": self.raster_height,
            }
        return payload

    def world_to_camera(self, point_m: Vec3) -> Vec3:
        forward, right, camera_up = self._basis()
        delta = _subtract(point_m, self.position_m)
        return (_dot(delta, right), _dot(delta, camera_up), _dot(delta, forward))

    @property
    def raster_width(self) -> int:
        return self.visibility_width or self.image_width

    @property
    def raster_height(self) -> int:
        return self.visibility_height or self.image_height

    @property
    def raster_fx(self) -> float:
        return self.fx * self.raster_width / self.image_width

    @property
    def raster_fy(self) -> float:
        return self.fy * self.raster_height / self.image_height

    @property
    def raster_cx(self) -> float:
        return self.cx * self.raster_width / self.image_width

    @property
    def raster_cy(self) -> float:
        return self.cy * self.raster_height / self.image_height

    def _basis(self) -> tuple[Vec3, Vec3, Vec3]:
        yaw = math.radians(self.yaw_degrees)
        pitch = math.radians(self.pitch_degrees)
        forward = _normalize(
            (
                math.cos(pitch) * math.sin(yaw),
                math.cos(pitch) * math.cos(yaw),
                math.sin(pitch),
            )
        )
        right = _normalize(_cross(forward, (0.0, 0.0, 1.0)))
        camera_up = _normalize(_cross(right, forward))
        return forward, right, camera_up


@dataclass(frozen=True)
class VehicleBox:
    vehicle_id: str
    vehicle_type: str
    front_bumper_m: Vec3
    angle_degrees: float
    length_m: float
    width_m: float
    height_m: float
    ground_clearance_m: float
    lane_id: str = ""
    road_id: str = ""
    pos_lat_m: float = 0.0

    def __post_init__(self) -> None:
        if not self.vehicle_id:
            raise GeometryContractError("vehicle_id must not be empty")
        if min(self.length_m, self.width_m, self.height_m) <= 0:
            raise GeometryContractError(f"{self.vehicle_id}: vehicle dimensions must be positive")
        if self.ground_clearance_m < 0:
            raise GeometryContractError(f"{self.vehicle_id}: ground clearance cannot be negative")

    @classmethod
    def from_trace_row(cls, row: dict[str, Any]) -> VehicleBox:
        required = (
            "vehicle_id",
            "vehicle_type",
            "x",
            "y",
            "angle",
            "length_m",
            "width_m",
            "height_m",
            "ground_clearance_m",
            "elevation_m",
            "reference_point",
        )
        missing = [field for field in required if field not in row]
        if missing:
            raise GeometryContractError(
                "Geometry camera requires canonical trace fields: " + ", ".join(missing)
            )
        if str(row["reference_point"]) != "front_bumper_center":
            raise GeometryContractError(
                f"Unsupported vehicle reference_point={row['reference_point']}"
            )
        return cls(
            vehicle_id=str(row["vehicle_id"]),
            vehicle_type=str(row["vehicle_type"]),
            front_bumper_m=(
                float(row["x"]),
                float(row["y"]),
                float(row["elevation_m"]),
            ),
            angle_degrees=float(row["angle"]),
            length_m=float(row["length_m"]),
            width_m=float(row["width_m"]),
            height_m=float(row["height_m"]),
            ground_clearance_m=float(row["ground_clearance_m"]),
            lane_id=str(row.get("lane_id", "")),
            road_id=str(row.get("road_id", "")),
            pos_lat_m=float(row.get("pos_lat_m", 0.0)),
        )

    @property
    def center_m(self) -> Vec3:
        forward = self._forward()
        return (
            self.front_bumper_m[0] - forward[0] * self.length_m / 2.0,
            self.front_bumper_m[1] - forward[1] * self.length_m / 2.0,
            self.front_bumper_m[2] + self.ground_clearance_m + self.height_m / 2.0,
        )

    def triangles_m(self) -> tuple[tuple[Vec3, Vec3, Vec3], ...]:
        center = self.center_m
        forward = self._forward()
        angle = math.radians(self.angle_degrees)
        right = (math.cos(angle), -math.sin(angle), 0.0)
        half_length = self.length_m / 2.0
        half_width = self.width_m / 2.0
        bottom_z = center[2] - self.height_m / 2.0
        top_z = center[2] + self.height_m / 2.0

        def point(longitudinal: float, lateral: float, z: float) -> Vec3:
            return (
                center[0] + forward[0] * longitudinal + right[0] * lateral,
                center[1] + forward[1] * longitudinal + right[1] * lateral,
                z,
            )

        corners = (
            point(-half_length, -half_width, bottom_z),
            point(half_length, -half_width, bottom_z),
            point(half_length, half_width, bottom_z),
            point(-half_length, half_width, bottom_z),
            point(-half_length, -half_width, top_z),
            point(half_length, -half_width, top_z),
            point(half_length, half_width, top_z),
            point(-half_length, half_width, top_z),
        )
        faces = (
            (0, 1, 2, 3),
            (4, 7, 6, 5),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (3, 7, 4, 0),
        )
        triangles: list[tuple[Vec3, Vec3, Vec3]] = []
        for a, b, c, d in faces:
            triangles.append((corners[a], corners[b], corners[c]))
            triangles.append((corners[a], corners[c], corners[d]))
        return tuple(triangles)

    def _forward(self) -> Vec3:
        angle = math.radians(self.angle_degrees)
        return (math.sin(angle), math.cos(angle), 0.0)


@dataclass(frozen=True)
class StaticOccluder:
    occluder_id: str
    triangles_m: tuple[tuple[Vec3, Vec3, Vec3], ...]


@dataclass(frozen=True)
class VisibilityRecord:
    time_seconds: float
    camera_id: str
    vehicle_id: str
    vehicle_type: str
    lane_id: str
    road_id: str
    in_fov: bool
    visibility_state: str
    visible_fraction: float
    occlusion_fraction: float
    depth_m: float | None
    visible_pixel_count: int
    projected_pixel_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": VISIBILITY_TRACE_SCHEMA_VERSION,
            "time_seconds": self.time_seconds,
            "camera_id": self.camera_id,
            "vehicle_id": self.vehicle_id,
            "vehicle_type": self.vehicle_type,
            "lane_id": self.lane_id,
            "road_id": self.road_id,
            "in_fov": self.in_fov,
            "visibility_state": self.visibility_state,
            "visible_fraction": round(self.visible_fraction, 6),
            "occlusion_fraction": round(self.occlusion_fraction, 6),
            "depth_m": round(self.depth_m, 6) if self.depth_m is not None else None,
            "visible_pixel_count": self.visible_pixel_count,
            "projected_pixel_count": self.projected_pixel_count,
        }


def load_camera_calibrations(path: Path) -> tuple[CameraCalibration, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GeometryContractError("camera calibration document must be an object")
    if str(payload.get("schema_version", "")) != CAMERA_CALIBRATION_SCHEMA_VERSION:
        raise GeometryContractError("camera calibration document has an unsupported schema_version")
    raw_cameras = payload.get("cameras", [])
    if not isinstance(raw_cameras, list):
        raise GeometryContractError("camera calibration document cameras must be an array")
    cameras = tuple(
        CameraCalibration.from_dict(row) for row in raw_cameras if isinstance(row, dict)
    )
    if not cameras:
        raise GeometryContractError("camera calibration document must contain at least one camera")
    if len({camera.camera_id for camera in cameras}) != len(cameras):
        raise GeometryContractError(
            "camera calibration document contains duplicate camera_id values"
        )
    return cameras


def write_camera_calibrations(cameras: Iterable[CameraCalibration], path: Path) -> None:
    serializable = [camera.to_dict() for camera in cameras]
    if not serializable:
        raise GeometryContractError("cannot write an empty camera calibration document")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": CAMERA_CALIBRATION_SCHEMA_VERSION,
                "coordinate_system": "sumo_xy_meters_z_up",
                "cameras": serializable,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def visibility_for_frame(
    *,
    camera: CameraCalibration,
    vehicles: Sequence[VehicleBox],
    time_seconds: float,
    static_occluders: Sequence[StaticOccluder] = (),
) -> tuple[VisibilityRecord, ...]:
    """Project vehicle cuboids into a deterministic software z-buffer."""

    ordered = tuple(sorted(vehicles, key=lambda vehicle: vehicle.vehicle_id))
    pixel_count = camera.raster_width * camera.raster_height
    depth_buffer = [math.inf] * pixel_count
    owner_buffer = [-1] * pixel_count
    projected_pixels: list[set[int]] = [set() for _ in ordered]
    nearest_projected_depth = [math.inf] * len(ordered)

    for occluder in sorted(static_occluders, key=lambda item: item.occluder_id):
        for triangle in occluder.triangles_m:
            _rasterize_world_triangle(
                camera=camera,
                triangle=triangle,
                owner=-2,
                coverage=None,
                nearest_depth=None,
                depth_buffer=depth_buffer,
                owner_buffer=owner_buffer,
            )

    for index, vehicle in enumerate(ordered):
        if not _may_project_vehicle(camera, vehicle):
            continue
        for triangle in vehicle.triangles_m():
            _rasterize_world_triangle(
                camera=camera,
                triangle=triangle,
                owner=index,
                coverage=projected_pixels[index],
                nearest_depth=nearest_projected_depth,
                depth_buffer=depth_buffer,
                owner_buffer=owner_buffer,
            )

    visible_pixels = [0] * len(ordered)
    nearest_visible_depth = [math.inf] * len(ordered)
    for pixel, owner in enumerate(owner_buffer):
        if owner < 0:
            continue
        visible_pixels[owner] += 1
        nearest_visible_depth[owner] = min(nearest_visible_depth[owner], depth_buffer[pixel])

    records: list[VisibilityRecord] = []
    for index, vehicle in enumerate(ordered):
        projected_count = len(projected_pixels[index])
        visible_count = visible_pixels[index]
        if projected_count == 0:
            state = "out_of_fov"
            in_fov = False
            visible_fraction = 0.0
            occlusion_fraction = 0.0
            depth_m: float | None = None
        else:
            in_fov = True
            visible_fraction = visible_count / projected_count
            occlusion_fraction = 1.0 - visible_fraction
            if visible_count == 0:
                state = "fully_occluded"
                depth_m = (
                    nearest_projected_depth[index]
                    if math.isfinite(nearest_projected_depth[index])
                    else None
                )
            elif visible_count == projected_count:
                state = "visible"
                depth_m = nearest_visible_depth[index]
            else:
                state = "partially_occluded"
                depth_m = nearest_visible_depth[index]
        records.append(
            VisibilityRecord(
                time_seconds=time_seconds,
                camera_id=camera.camera_id,
                vehicle_id=vehicle.vehicle_id,
                vehicle_type=vehicle.vehicle_type,
                lane_id=vehicle.lane_id,
                road_id=vehicle.road_id,
                in_fov=in_fov,
                visibility_state=state,
                visible_fraction=visible_fraction,
                occlusion_fraction=occlusion_fraction,
                depth_m=depth_m,
                visible_pixel_count=visible_count,
                projected_pixel_count=projected_count,
            )
        )
    return tuple(records)


def visibility_from_trace_frames(
    *,
    frames: Iterable[dict[str, Any]],
    cameras: Iterable[CameraCalibration],
    static_occluders: Sequence[StaticOccluder] = (),
) -> tuple[VisibilityRecord, ...]:
    camera_list = tuple(cameras)
    records: list[VisibilityRecord] = []
    for frame in frames:
        if str(frame.get("schema_version", "")) != "vehicle_trace.v2":
            raise GeometryContractError(
                "Geometry camera requires vehicle_trace.v2; legacy traces must be regenerated."
            )
        raw_vehicles = frame.get("vehicles", [])
        if not isinstance(raw_vehicles, list):
            raise GeometryContractError("vehicle trace frame vehicles must be an array")
        vehicles = tuple(
            VehicleBox.from_trace_row(row) for row in raw_vehicles if isinstance(row, dict)
        )
        time_seconds = float(frame.get("time_seconds", 0.0))
        for camera in camera_list:
            records.extend(
                visibility_for_frame(
                    camera=camera,
                    vehicles=vehicles,
                    time_seconds=time_seconds,
                    static_occluders=static_occluders,
                )
            )
    return tuple(records)


def write_visibility_trace(records: Iterable[VisibilityRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


@dataclass(frozen=True)
class GeometrySensorObservation:
    sensor_id: str
    timestamp_seconds: float
    estimated_count_by_approach: dict[str, int]
    class_mix_by_approach: dict[str, dict[str, int]]
    visible_fraction_by_approach: dict[str, float]
    observation_confidence_by_approach: dict[str, float]
    time_since_last_observed_by_approach: dict[str, float]
    detector_unknown_count_by_approach: dict[str, int]
    sensor_mode: str = "geometry_visibility"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SENSOR_OBSERVATION_SCHEMA_VERSION,
            "sensor_id": self.sensor_id,
            "timestamp_seconds": self.timestamp_seconds,
            "sensor_mode": self.sensor_mode,
            "estimated_count_by_approach": self.estimated_count_by_approach,
            "class_mix_by_approach": self.class_mix_by_approach,
            "visible_fraction_by_approach": self.visible_fraction_by_approach,
            "observation_confidence_by_approach": self.observation_confidence_by_approach,
            "time_since_last_observed_by_approach": self.time_since_last_observed_by_approach,
            "detector_unknown_count_by_approach": self.detector_unknown_count_by_approach,
        }


@dataclass
class GeometryObservationAdapter:
    """Aggregate only visible records; internal identities never leave the adapter."""

    sensor_id: str
    lane_to_approach: dict[str, str]
    visible_threshold: float = 0.02
    _last_reliable_time: dict[str, float] = field(default_factory=dict, init=False)
    _first_timestamp: float | None = field(default=None, init=False)

    def observe(
        self,
        *,
        timestamp_seconds: float,
        records: Iterable[VisibilityRecord],
    ) -> GeometrySensorObservation:
        if self._first_timestamp is None:
            self._first_timestamp = timestamp_seconds
        approaches = tuple(sorted(set(self.lane_to_approach.values())))
        counts = {approach: 0 for approach in approaches}
        classes: dict[str, dict[str, int]] = {approach: {} for approach in approaches}
        fractions: dict[str, list[float]] = {approach: [] for approach in approaches}

        for record in records:
            if (
                record.camera_id != self.sensor_id
                or record.visible_fraction < self.visible_threshold
            ):
                continue
            approach = self.lane_to_approach.get(record.lane_id)
            if approach is None:
                continue
            counts[approach] += 1
            classes[approach][record.vehicle_type] = (
                classes[approach].get(record.vehicle_type, 0) + 1
            )
            fractions[approach].append(record.visible_fraction)
            self._last_reliable_time[approach] = timestamp_seconds

        visible_fraction = {
            approach: round(sum(values) / len(values), 6) if values else 0.0
            for approach, values in fractions.items()
        }
        started_at = (
            self._first_timestamp if self._first_timestamp is not None else timestamp_seconds
        )
        age = {
            approach: round(
                timestamp_seconds - self._last_reliable_time.get(approach, started_at),
                6,
            )
            for approach in approaches
        }
        return GeometrySensorObservation(
            sensor_id=self.sensor_id,
            timestamp_seconds=timestamp_seconds,
            estimated_count_by_approach=counts,
            class_mix_by_approach=classes,
            visible_fraction_by_approach=visible_fraction,
            observation_confidence_by_approach=visible_fraction.copy(),
            time_since_last_observed_by_approach=age,
            detector_unknown_count_by_approach={approach: 0 for approach in approaches},
        )


def _rasterize_world_triangle(
    *,
    camera: CameraCalibration,
    triangle: tuple[Vec3, Vec3, Vec3],
    owner: int,
    coverage: set[int] | None,
    nearest_depth: list[float] | None,
    depth_buffer: list[float],
    owner_buffer: list[int],
) -> None:
    polygon = [camera.world_to_camera(point) for point in triangle]
    polygon = _clip_depth(polygon, camera.near_clip_m, keep_greater=True)
    polygon = _clip_depth(polygon, camera.far_clip_m, keep_greater=False)
    if len(polygon) < 3:
        return
    for index in range(1, len(polygon) - 1):
        _rasterize_camera_triangle(
            camera=camera,
            triangle=(polygon[0], polygon[index], polygon[index + 1]),
            owner=owner,
            coverage=coverage,
            nearest_depth=nearest_depth,
            depth_buffer=depth_buffer,
            owner_buffer=owner_buffer,
        )


def _rasterize_camera_triangle(
    *,
    camera: CameraCalibration,
    triangle: tuple[Vec3, Vec3, Vec3],
    owner: int,
    coverage: set[int] | None,
    nearest_depth: list[float] | None,
    depth_buffer: list[float],
    owner_buffer: list[int],
) -> None:
    projected = tuple(_project_camera_point(camera, point) for point in triangle)
    (x0, y0), (x1, y1), (x2, y2) = projected
    area = _edge((x0, y0), (x1, y1), (x2, y2))
    if abs(area) <= _EPSILON:
        return
    min_x = max(0, math.floor(min(x0, x1, x2)))
    max_x = min(camera.raster_width - 1, math.ceil(max(x0, x1, x2)))
    min_y = max(0, math.floor(min(y0, y1, y2)))
    max_y = min(camera.raster_height - 1, math.ceil(max(y0, y1, y2)))
    if min_x > max_x or min_y > max_y:
        return

    z0, z1, z2 = triangle[0][2], triangle[1][2], triangle[2][2]
    for pixel_y in range(min_y, max_y + 1):
        for pixel_x in range(min_x, max_x + 1):
            point = (pixel_x + 0.5, pixel_y + 0.5)
            w0 = _edge((x1, y1), (x2, y2), point) / area
            w1 = _edge((x2, y2), (x0, y0), point) / area
            w2 = 1.0 - w0 - w1
            if min(w0, w1, w2) < -_EPSILON:
                continue
            inverse_depth = w0 / z0 + w1 / z1 + w2 / z2
            if inverse_depth <= 0:
                continue
            depth = 1.0 / inverse_depth
            buffer_index = pixel_y * camera.raster_width + pixel_x
            if coverage is not None:
                coverage.add(buffer_index)
            if nearest_depth is not None and owner >= 0:
                nearest_depth[owner] = min(nearest_depth[owner], depth)
            current_depth = depth_buffer[buffer_index]
            current_owner = owner_buffer[buffer_index]
            if depth < current_depth - _EPSILON or (
                abs(depth - current_depth) <= _EPSILON
                and (current_owner < 0 or owner < current_owner)
            ):
                depth_buffer[buffer_index] = depth
                owner_buffer[buffer_index] = owner


def _clip_depth(polygon: list[Vec3], boundary: float, *, keep_greater: bool) -> list[Vec3]:
    if not polygon:
        return []

    def kept(point: Vec3) -> bool:
        return point[2] >= boundary if keep_greater else point[2] <= boundary

    clipped: list[Vec3] = []
    previous = polygon[-1]
    previous_kept = kept(previous)
    for current in polygon:
        current_kept = kept(current)
        if current_kept != previous_kept:
            denominator = current[2] - previous[2]
            if abs(denominator) > _EPSILON:
                alpha = (boundary - previous[2]) / denominator
                clipped.append(
                    (
                        previous[0] + alpha * (current[0] - previous[0]),
                        previous[1] + alpha * (current[1] - previous[1]),
                        boundary,
                    )
                )
        if current_kept:
            clipped.append(current)
        previous = current
        previous_kept = current_kept
    return clipped


def _project_camera_point(camera: CameraCalibration, point: Vec3) -> tuple[float, float]:
    return (
        camera.raster_cx + camera.raster_fx * point[0] / point[2],
        camera.raster_cy - camera.raster_fy * point[1] / point[2],
    )


def _may_project_vehicle(camera: CameraCalibration, vehicle: VehicleBox) -> bool:
    center = camera.world_to_camera(vehicle.center_m)
    radius = math.sqrt(
        (vehicle.length_m / 2.0) ** 2 + (vehicle.width_m / 2.0) ** 2 + (vehicle.height_m / 2.0) ** 2
    )
    if center[2] + radius < camera.near_clip_m or center[2] - radius > camera.far_clip_m:
        return False
    depth = max(camera.near_clip_m, center[2])
    half_width = depth * camera.image_width / (2.0 * camera.fx)
    half_height = depth * camera.image_height / (2.0 * camera.fy)
    return abs(center[0]) - radius <= half_width and abs(center[1]) - radius <= half_height


def _vec3(value: object, field_name: str) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise GeometryContractError(f"{field_name} must be a three-value array")
    return (float(value[0]), float(value[1]), float(value[2]))


def _edge(a: tuple[float, float], b: tuple[float, float], point: tuple[float, float]) -> float:
    return (point[0] - a[0]) * (b[1] - a[1]) - (point[1] - a[1]) * (b[0] - a[0])


def _subtract(left: Vec3, right: Vec3) -> Vec3:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _dot(left: Vec3, right: Vec3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _cross(left: Vec3, right: Vec3) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalize(value: Vec3) -> Vec3:
    magnitude = math.sqrt(_dot(value, value))
    if magnitude <= _EPSILON:
        raise GeometryContractError("camera basis is degenerate")
    return (value[0] / magnitude, value[1] / magnitude, value[2] / magnitude)
