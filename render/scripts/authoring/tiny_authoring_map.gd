@tool
class_name TinyAuthoringMap
extends Node3D

@export var build_roads_on_ready := true
@export var rebuild_roads := false:
	set(value):
		rebuild_roads = false
		if is_inside_tree():
			rebuild_roads_preview()

var road_count := 0


func _ready() -> void:
	if build_roads_on_ready:
		call_deferred("rebuild_roads_preview")


func rebuild_roads_preview() -> void:
	_clear_roads()
	_add_ground()
	_add_road("Road_Main_EW", Vector3.ZERO, Vector3(36.0, 0.10, 3.4), 0.0)
	_add_road("Road_Main_NS", Vector3.ZERO, Vector3(3.4, 0.11, 36.0), 0.0)
	_add_road("Road_North_EW", Vector3(0.0, 0.0, -11.5), Vector3(30.0, 0.08, 2.1), 0.0)
	_add_road("Road_West_NS", Vector3(-11.5, 0.0, 0.0), Vector3(2.1, 0.09, 30.0), 0.0)
	_add_intersection(Vector3.ZERO)


func summary() -> Dictionary:
	var zones := get_tree().get_nodes_in_group("zone_lot_authoring")
	var building_total := 0
	for zone in zones:
		if zone.has_method("building_visual_count"):
			building_total += int(zone.building_visual_count())
	return {
		"road_count": road_count,
		"zone_lot_count": zones.size(),
		"building_visual_count": building_total,
	}


func _add_ground() -> void:
	var ground := MeshInstance3D.new()
	ground.name = "GeneratedAuthoringGround"
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(46.0, 46.0)
	ground.mesh = mesh
	ground.set_surface_override_material(0, _material(Color(0.40, 0.48, 0.39, 1.0)))
	_mark_generated(ground)
	add_child(ground)


func _add_road(road_name: String, road_position: Vector3, road_size: Vector3, road_rotation_y: float) -> void:
	var road := MeshInstance3D.new()
	road.name = road_name
	var mesh := BoxMesh.new()
	mesh.size = road_size
	road.mesh = mesh
	road.position = Vector3(road_position.x, 0.06, road_position.z)
	road.rotation.y = road_rotation_y
	road.set_surface_override_material(0, _material(Color(0.06, 0.06, 0.065, 1.0)))
	_mark_generated(road)
	add_child(road)
	road_count += 1
	_add_lane_marking("%s_Midline" % road_name, road_position, road_size)


func _add_lane_marking(marking_name: String, road_position: Vector3, road_size: Vector3) -> void:
	var marking := MeshInstance3D.new()
	marking.name = marking_name
	var mesh := BoxMesh.new()
	if road_size.x >= road_size.z:
		mesh.size = Vector3(road_size.x * 0.92, 0.015, 0.05)
	else:
		mesh.size = Vector3(0.05, 0.015, road_size.z * 0.92)
	marking.mesh = mesh
	marking.position = Vector3(road_position.x, 0.125, road_position.z)
	marking.set_surface_override_material(0, _material(Color(0.95, 0.88, 0.28, 1.0)))
	_mark_generated(marking)
	add_child(marking)


func _add_intersection(center: Vector3) -> void:
	var marker := MeshInstance3D.new()
	marker.name = "GeneratedCentralIntersection"
	var mesh := CylinderMesh.new()
	mesh.top_radius = 2.35
	mesh.bottom_radius = 2.35
	mesh.height = 0.12
	mesh.radial_segments = 32
	marker.mesh = mesh
	marker.position = Vector3(center.x, 0.14, center.z)
	marker.set_surface_override_material(0, _material(Color(0.035, 0.035, 0.04, 1.0)))
	_mark_generated(marker)
	add_child(marker)


func _clear_roads() -> void:
	for child in get_children():
		if child.is_in_group("tiny_authoring_generated_roads"):
			child.queue_free()
	road_count = 0


func _mark_generated(node: Node) -> void:
	node.add_to_group("tiny_authoring_generated_roads")


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	return material
