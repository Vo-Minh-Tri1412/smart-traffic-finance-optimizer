class_name CoordinateMapper
extends RefCounted

var scale := 0.02
var center := Vector2.ZERO
var bounds_min := Vector2.ZERO
var bounds_max := Vector2.ZERO


func configure(trace_bounds_min: Vector2, trace_bounds_max: Vector2, render_scale: float = 0.02) -> void:
	bounds_min = trace_bounds_min
	bounds_max = trace_bounds_max
	scale = render_scale
	center = (bounds_min + bounds_max) / 2.0


func sumo_to_world(x: float, y: float, height: float = 0.25) -> Vector3:
	return Vector3((x - center.x) * scale, height, (y - center.y) * scale)


func world_to_sumo(position: Vector3) -> Vector2:
	return Vector2(position.x / max(0.000001, scale) + center.x, position.z / max(0.000001, scale) + center.y)


func sumo_angle_to_yaw(angle_degrees: float) -> float:
	return deg_to_rad(90.0 - angle_degrees)


func mapped_width() -> float:
	return abs(bounds_max.x - bounds_min.x) * scale


func mapped_depth() -> float:
	return abs(bounds_max.y - bounds_min.y) * scale
