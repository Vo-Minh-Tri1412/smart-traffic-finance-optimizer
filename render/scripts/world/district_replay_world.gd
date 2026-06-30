class_name DistrictReplayWorld
extends Node3D

const CoordinateMapperScript := preload("res://scripts/replay/coordinate_mapper.gd")
const SumoNetGeometryDataScript := preload("res://scripts/world/sumo_net_geometry_data.gd")

@export var spec_path := ""
@export var net_path := ""
@export var world_scale := 0.02
@export var sumo_meters_per_spec_unit := 1000.0
@export var road_width := 1.6
@export var lane_width_m := 3.2

var intersection_positions: Dictionary = {}
var road_count := 0
var intersection_count := 0
var lane_count := 0
var _spec_center := Vector2.ZERO
var _sumo_geometry = null
var _sumo_bounds_min := Vector2.ZERO
var _sumo_bounds_max := Vector2.ZERO
var _has_sumo_geometry := false
var _mapper = null


func _ready() -> void:
	if not net_path.is_empty():
		build_from_sumo_net(net_path)
	elif not spec_path.is_empty():
		build_from_spec(spec_path)


func build_from_spec(path: String) -> bool:
	_clear_generated()
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_warning("District spec not found for Godot world: %s" % path)
		return false
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("District spec is not a JSON object: %s" % path)
		return false
	var spec := parsed as Dictionary
	_build_intersections(spec.get("intersections", []))
	_build_roads(spec.get("roads", []))
	return true


func build_from_sumo_net(path: String) -> bool:
	_clear_generated()
	_sumo_geometry = SumoNetGeometryDataScript.new()
	if not _sumo_geometry.load_xml(path):
		for error in _sumo_geometry.errors:
			push_warning(error)
		return false

	_configure_sumo_bounds(_sumo_geometry)
	for lane in _sumo_geometry.lanes:
		_build_sumo_lane(lane)
	for junction in _sumo_geometry.junctions:
		_build_sumo_junction(junction)
	return true


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_world_object"):
			child.queue_free()
	intersection_positions.clear()
	road_count = 0
	intersection_count = 0
	lane_count = 0
	_sumo_geometry = null
	_sumo_bounds_min = Vector2.ZERO
	_sumo_bounds_max = Vector2.ZERO
	_has_sumo_geometry = false
	_mapper = null


func _build_intersections(intersections: Array) -> void:
	_spec_center = _intersection_center(intersections)
	for item in intersections:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var row := item as Dictionary
		var intersection_id := String(row.get("id", ""))
		if intersection_id.is_empty():
			continue
		var sumo_x := float(row.get("x", 0.0)) * sumo_meters_per_spec_unit
		var sumo_y := float(row.get("y", 0.0)) * sumo_meters_per_spec_unit
		var position := Vector3(
			(sumo_x - _spec_center.x) * world_scale,
			0.05,
			(sumo_y - _spec_center.y) * world_scale
		)
		intersection_positions[intersection_id] = position
		var marker := MeshInstance3D.new()
		marker.name = "Intersection_%s" % intersection_id
		marker.mesh = _cylinder_mesh(1.9, 0.12)
		marker.position = position
		marker.set_surface_override_material(0, _material(Color(0.08, 0.09, 0.10)))
		marker.add_to_group("generated_world_object")
		add_child(marker)
		intersection_count += 1


func _build_roads(roads: Array) -> void:
	for item in roads:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var row := item as Dictionary
		var from_id := String(row.get("from", ""))
		var to_id := String(row.get("to", ""))
		if not intersection_positions.has(from_id) or not intersection_positions.has(to_id):
			continue
		var start := intersection_positions[from_id] as Vector3
		var end := intersection_positions[to_id] as Vector3
		var midpoint := (start + end) / 2.0
		var direction := end - start
		var length: float = direction.length()
		if length < 0.1:
			length = 0.1
		var lanes: int = int(row.get("lanes", 1))
		if lanes < 1:
			lanes = 1

		var road := MeshInstance3D.new()
		road.name = "Road_%s" % String(row.get("id", "unknown"))
		var mesh := BoxMesh.new()
		mesh.size = Vector3(road_width * lanes, 0.04, length)
		road.mesh = mesh
		road.position = Vector3(midpoint.x, 0.0, midpoint.z)
		road.rotation.y = atan2(direction.x, direction.z)
		road.set_surface_override_material(0, _material(Color(0.18, 0.18, 0.18)))
		road.add_to_group("generated_world_object")
		add_child(road)
		road_count += 1


func _cylinder_mesh(radius: float, height: float) -> CylinderMesh:
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 24
	return mesh


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	return material


func _build_sumo_lane(lane_geometry) -> void:
	var lane_material := _material(Color(0.16, 0.16, 0.16))
	var lane_id := String(lane_geometry.lane_id)
	var points: Array = lane_geometry.points
	for index in range(points.size() - 1):
		var start := points[index] as Vector2
		var end := points[index + 1] as Vector2
		var direction := end - start
		var length_m := direction.length()
		if length_m < 0.1:
			continue
		var midpoint := (start + end) / 2.0
		var lane_mesh := MeshInstance3D.new()
		lane_mesh.name = "Lane_%s_%d" % [lane_id, index]
		var mesh := BoxMesh.new()
		mesh.size = Vector3(max(0.08, lane_width_m * world_scale), 0.035, length_m * world_scale)
		lane_mesh.mesh = mesh
		lane_mesh.position = _mapper.sumo_to_world(midpoint.x, midpoint.y, 0.02)
		lane_mesh.rotation.y = atan2(direction.x, direction.y)
		lane_mesh.set_surface_override_material(0, lane_material)
		lane_mesh.add_to_group("generated_world_object")
		add_child(lane_mesh)
	lane_count += 1
	road_count += 1


func _build_sumo_junction(junction) -> void:
	var marker := MeshInstance3D.new()
	marker.name = "Junction_%s" % String(junction.junction_id)
	marker.mesh = _cylinder_mesh(0.22, 0.08)
	marker.position = _mapper.sumo_to_world(junction.point.x, junction.point.y, 0.05)
	marker.set_surface_override_material(0, _material(Color(0.05, 0.05, 0.05)))
	marker.add_to_group("generated_world_object")
	add_child(marker)
	intersection_count += 1


func _configure_sumo_bounds(geometry) -> void:
	_sumo_bounds_min = geometry.bounds_min
	_sumo_bounds_max = geometry.bounds_max
	_mapper = CoordinateMapperScript.new()
	_mapper.configure(_sumo_bounds_min, _sumo_bounds_max, world_scale)
	_has_sumo_geometry = true


func has_geometry_bounds() -> bool:
	return _has_sumo_geometry


func get_geometry_bounds_min() -> Vector2:
	return _sumo_bounds_min


func get_geometry_bounds_max() -> Vector2:
	return _sumo_bounds_max


func distance_to_nearest_lane_m(x: float, y: float) -> float:
	if _sumo_geometry == null:
		return 0.0
	return float(_sumo_geometry.distance_to_nearest_lane_m(Vector2(x, y)))


func geometry_data_model() -> String:
	return "SumoNetGeometryData" if _sumo_geometry != null else "spec_fallback"


func _intersection_center(intersections: Array) -> Vector2:
	var has_value := false
	var min_value := Vector2.ZERO
	var max_value := Vector2.ZERO
	for item in intersections:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var row := item as Dictionary
		var point := Vector2(
			float(row.get("x", 0.0)) * sumo_meters_per_spec_unit,
			float(row.get("y", 0.0)) * sumo_meters_per_spec_unit
		)
		if not has_value:
			min_value = point
			max_value = point
			has_value = true
		else:
			min_value.x = min(min_value.x, point.x)
			min_value.y = min(min_value.y, point.y)
			max_value.x = max(max_value.x, point.x)
			max_value.y = max(max_value.y, point.y)
	return (min_value + max_value) / 2.0 if has_value else Vector2.ZERO
