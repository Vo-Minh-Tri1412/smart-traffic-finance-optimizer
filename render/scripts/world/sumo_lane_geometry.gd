class_name SumoLaneGeometry
extends RefCounted

var lane_id := ""
var edge_id := ""
var width_m := 3.2
var points: Array[Vector2] = []


func configure(id: String, parent_edge_id: String, shape_points: Array[Vector2], lane_width_m: float) -> void:
	lane_id = id
	edge_id = parent_edge_id
	width_m = lane_width_m
	points = shape_points.duplicate()


func is_valid() -> bool:
	return not lane_id.is_empty() and points.size() >= 2


func distance_to_point_m(point: Vector2) -> float:
	if points.size() < 2:
		return INF
	var best := INF
	for index in range(points.size() - 1):
		best = min(best, _distance_point_to_segment(point, points[index], points[index + 1]))
	return max(0.0, best - width_m / 2.0)


func _distance_point_to_segment(point: Vector2, start: Vector2, end: Vector2) -> float:
	var segment := end - start
	var length_squared := segment.length_squared()
	if length_squared <= 0.000001:
		return point.distance_to(start)
	var t: float = clamp((point - start).dot(segment) / length_squared, 0.0, 1.0)
	return point.distance_to(start + segment * t)
