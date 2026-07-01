@tool
class_name RoadSegment
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var road_id := ""
@export_node_path("Node3D") var from_intersection_path: NodePath = NodePath("")
@export var from_intersection := ""
@export_node_path("Node3D") var to_intersection_path: NodePath = NodePath("")
@export var to_intersection := ""
@export var bidirectional := true
@export var lanes := 2
@export var lane_width_m := 3.2
@export var sidewalk_width_m := 1.5
@export var median_width_m := 0.0
@export var speed_kph := 40.0
@export var capacity := 900.0
@export var truck_allowed := true
@export var tags: Array[String] = []
@export var length_km_override := 0.0
@export var shape_points: PackedVector3Array = PackedVector3Array()

const PREVIEW_PREFIX := "_RoadPreviewSegment"
const PREVIEW_HEIGHT_M := 0.35

var _last_preview_signature := ""


func _ready() -> void:
	_register_authoring_marker("authoring_road")
	if Engine.is_editor_hint():
		set_process(true)
		_refresh_preview_if_needed(true)


func _process(_delta: float) -> void:
	if Engine.is_editor_hint():
		_refresh_preview_if_needed(false)


func to_authoring_rows(context: Dictionary = {}) -> Array:
	var intersections := context.get("intersections", {}) as Dictionary
	var from_id := _resolved_intersection_id(from_intersection_path, from_intersection)
	var to_id := _resolved_intersection_id(to_intersection_path, to_intersection)
	if road_id.is_empty() or from_id.is_empty() or to_id.is_empty():
		push_error("%s: road_id and both road endpoints are required" % get_path())
		return []
	if not intersections.has(from_id) or not intersections.has(to_id):
		push_error("%s: road endpoint not found: %s -> %s" % [road_id, from_id, to_id])
		return []

	var shape_points_km := _shape_points_km(intersections[from_id], intersections[to_id])
	var length_km := _road_length_km(intersections[from_id], intersections[to_id])
	var rows := [_road_row(road_id, from_id, to_id, length_km, shape_points_km)]
	if bidirectional:
		var reverse_shape := shape_points_km.duplicate()
		reverse_shape.reverse()
		rows.append(_road_row("%s_REV" % road_id, to_id, from_id, length_km, reverse_shape))
	return rows


func _road_row(
	actual_road_id: String,
	from_id: String,
	to_id: String,
	length_km: float,
	shape_points_km: Array,
) -> Dictionary:
	return {
		"id": actual_road_id,
		"from": from_id,
		"to": to_id,
		"length_km": length_km,
		"speed_kph": speed_kph,
		"lanes": lanes,
		"lane_width_m": lane_width_m,
		"sidewalk_width_m": sidewalk_width_m,
		"median_width_m": median_width_m,
		"visual_width_m": _visual_width_m(),
		"capacity": capacity,
		"tags": string_array(tags),
		"truck_allowed": truck_allowed,
		"shape_points": shape_points_km,
	}


func _road_length_km(from_row: Dictionary, to_row: Dictionary) -> float:
	if length_km_override > 0.0:
		return round3(length_km_override)
	var points := _path_points_m(from_row, to_row)
	var meters := 0.0
	for index in range(points.size() - 1):
		meters += points[index].distance_to(points[index + 1])
	return max(0.001, round3(meters / 1000.0))


func _resolved_intersection_id(path: NodePath, fallback_id: String) -> String:
	var from_node := node_id_from_path(path, "intersection_id")
	if from_node.is_empty():
		return fallback_id
	return from_node


func _path_points_m(from_row: Dictionary, to_row: Dictionary) -> Array[Vector3]:
	var from_point := Vector3(float(from_row["x"]) * 1000.0, 0.0, float(from_row["y"]) * 1000.0)
	var to_point := Vector3(float(to_row["x"]) * 1000.0, 0.0, float(to_row["y"]) * 1000.0)
	var points: Array[Vector3] = [from_point]
	for point in shape_points:
		points.append(point)
	points.append(to_point)
	return points


func _shape_points_km(from_row: Dictionary, to_row: Dictionary) -> Array:
	var output := []
	var points := _path_points_m(from_row, to_row)
	for index in range(1, points.size() - 1):
		output.append({"x": round3(points[index].x / 1000.0), "y": round3(points[index].z / 1000.0)})
	return output


func _visual_width_m() -> float:
	return max(1.0, float(lanes) * lane_width_m + sidewalk_width_m * 2.0 + median_width_m)


func _refresh_preview_if_needed(force: bool) -> void:
	var signature := _preview_signature()
	if force or signature != _last_preview_signature:
		_last_preview_signature = signature
		_rebuild_preview()


func _preview_signature() -> String:
	return "%s|%s|%s|%s|%s|%s|%s|%s" % [
		from_intersection_path,
		to_intersection_path,
		from_intersection,
		to_intersection,
		global_position,
		shape_points,
		lanes,
		_visual_width_m(),
	]


func _rebuild_preview() -> void:
	_clear_preview()
	var from_node := get_node_or_null(from_intersection_path)
	var to_node := get_node_or_null(to_intersection_path)
	if from_node == null or to_node == null:
		return
	if not (from_node is Node3D) or not (to_node is Node3D):
		return
	var points: Array[Vector3] = [(from_node as Node3D).global_position]
	for point in shape_points:
		points.append(point)
	points.append((to_node as Node3D).global_position)
	for index in range(points.size() - 1):
		_add_preview_segment(index, points[index], points[index + 1])


func _clear_preview() -> void:
	for child in get_children():
		if child.name.begins_with(PREVIEW_PREFIX):
			child.queue_free()


func _add_preview_segment(index: int, start: Vector3, finish: Vector3) -> void:
	var delta := finish - start
	var length := Vector2(delta.x, delta.z).length()
	if length <= 0.001:
		return
	var mesh := BoxMesh.new()
	mesh.size = Vector3(_visual_width_m(), PREVIEW_HEIGHT_M, length)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.08, 0.08, 0.08, 0.65)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	var instance := MeshInstance3D.new()
	instance.name = "%s_%02d" % [PREVIEW_PREFIX, index]
	instance.mesh = mesh
	instance.surface_material_override = material
	add_child(instance)
	var midpoint := (start + finish) * 0.5
	var yaw := atan2(delta.x, delta.z)
	instance.global_transform = Transform3D(Basis(Vector3.UP, yaw), midpoint + Vector3(0.0, 0.05, 0.0))
