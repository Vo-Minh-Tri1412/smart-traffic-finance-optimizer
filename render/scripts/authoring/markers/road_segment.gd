@tool
class_name RoadSegment
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var road_id := ""
@export var from_intersection := ""
@export var to_intersection := ""
@export var bidirectional := true
@export var lanes := 2
@export var speed_kph := 40.0
@export var capacity := 900.0
@export var truck_allowed := true
@export var tags: Array[String] = []
@export var length_km_override := 0.0
@export var shape_points: PackedVector3Array = PackedVector3Array()


func _ready() -> void:
	_register_authoring_marker("authoring_road")


func to_authoring_rows(context: Dictionary = {}) -> Array:
	var intersections := context.get("intersections", {}) as Dictionary
	if road_id.is_empty() or from_intersection.is_empty() or to_intersection.is_empty():
		push_error("%s: road_id/from_intersection/to_intersection are required" % get_path())
		return []
	if not intersections.has(from_intersection) or not intersections.has(to_intersection):
		push_error("%s: road endpoint not found: %s -> %s" % [road_id, from_intersection, to_intersection])
		return []

	var length_km := _road_length_km(intersections[from_intersection], intersections[to_intersection])
	var rows := [_road_row(road_id, from_intersection, to_intersection, length_km)]
	if bidirectional:
		rows.append(_road_row("%s_REV" % road_id, to_intersection, from_intersection, length_km))
	return rows


func _road_row(actual_road_id: String, from_id: String, to_id: String, length_km: float) -> Dictionary:
	return {
		"id": actual_road_id,
		"from": from_id,
		"to": to_id,
		"length_km": length_km,
		"speed_kph": speed_kph,
		"lanes": lanes,
		"capacity": capacity,
		"tags": string_array(tags),
		"truck_allowed": truck_allowed,
	}


func _road_length_km(from_row: Dictionary, to_row: Dictionary) -> float:
	if length_km_override > 0.0:
		return round3(length_km_override)
	var from_point := Vector3(float(from_row["x"]) * 1000.0, 0.0, float(from_row["y"]) * 1000.0)
	var to_point := Vector3(float(to_row["x"]) * 1000.0, 0.0, float(to_row["y"]) * 1000.0)
	var points: Array[Vector3] = [from_point]
	for point in shape_points:
		points.append(point)
	points.append(to_point)
	var meters := 0.0
	for index in range(points.size() - 1):
		meters += points[index].distance_to(points[index + 1])
	return max(0.001, round3(meters / 1000.0))
