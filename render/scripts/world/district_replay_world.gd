class_name DistrictReplayWorld
extends Node3D

@export var spec_path := ""
@export var world_scale := 0.02
@export var sumo_meters_per_spec_unit := 1000.0
@export var road_width := 1.6

var intersection_positions: Dictionary = {}
var road_count := 0
var intersection_count := 0
var _spec_center := Vector2.ZERO


func _ready() -> void:
	if not spec_path.is_empty():
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


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_world_object"):
			child.queue_free()
	intersection_positions.clear()
	road_count = 0
	intersection_count = 0


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
