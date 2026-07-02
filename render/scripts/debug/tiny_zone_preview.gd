class_name TinyZonePreview
extends Node3D

const ZoneVisualFactoryScript := preload("res://scripts/assets/zone_visual_factory.gd")

@export var zone_catalog_path := "res://resources/catalogs/ZoneAssetCatalog.tres"
@export var vehicle_catalog_path := "res://resources/catalogs/VehicleAssetCatalog.tres"
@export var build_on_ready := true

var spawned_zone_count := 0
var spawned_vehicle_count := 0
var road_count := 0
var intersection_count := 0


func _ready() -> void:
	if build_on_ready:
		build_preview()


func build_preview() -> Dictionary:
	_clear_generated()
	_add_ground()
	_add_roads()
	_add_zones()
	_add_sample_vehicles()
	return summary()


func summary() -> Dictionary:
	return {
		"spawned_zone_count": spawned_zone_count,
		"building_visual_count": _count_building_visuals(),
		"spawned_vehicle_count": spawned_vehicle_count,
		"road_count": road_count,
		"intersection_count": intersection_count,
		"zone_catalog_path": zone_catalog_path,
		"vehicle_catalog_path": vehicle_catalog_path,
	}


func _add_ground() -> void:
	var ground := MeshInstance3D.new()
	ground.name = "PreviewGround"
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(44.0, 44.0)
	ground.mesh = mesh
	ground.position = Vector3.ZERO
	ground.set_surface_override_material(0, _material(Color(0.42, 0.48, 0.42)))
	_mark_generated(ground)
	add_child(ground)


func _add_roads() -> void:
	_add_road("Road_EastWest_Main", Vector3.ZERO, Vector3(38.0, 0.08, 3.6), 0.0)
	_add_road("Road_NorthSouth_Main", Vector3.ZERO, Vector3(3.6, 0.09, 38.0), 0.0)
	_add_road("Road_EastWest_Side", Vector3(0.0, 0.02, -10.0), Vector3(34.0, 0.06, 2.2), 0.0)
	_add_road("Road_NorthSouth_Side", Vector3(-10.0, 0.03, 0.0), Vector3(2.2, 0.07, 34.0), 0.0)
	_add_intersection_marker(Vector3.ZERO, 2.4)


func _add_road(road_name: String, road_position: Vector3, road_size: Vector3, road_rotation_y: float) -> void:
	var road := MeshInstance3D.new()
	road.name = road_name
	var mesh := BoxMesh.new()
	mesh.size = road_size
	road.mesh = mesh
	road.position = Vector3(road_position.x, 0.04, road_position.z)
	road.rotation.y = road_rotation_y
	road.set_surface_override_material(0, _material(Color(0.07, 0.07, 0.075)))
	_mark_generated(road)
	add_child(road)
	road_count += 1
	_add_lane_marking("%s_Marking_A" % road_name, road_position, road_size, -0.55, road_rotation_y)
	_add_lane_marking("%s_Marking_B" % road_name, road_position, road_size, 0.55, road_rotation_y)


func _add_lane_marking(
	marking_name: String,
	road_position: Vector3,
	road_size: Vector3,
	offset: float,
	road_rotation_y: float
) -> void:
	var marking := MeshInstance3D.new()
	marking.name = marking_name
	var mesh := BoxMesh.new()
	if road_size.x > road_size.z:
		mesh.size = Vector3(road_size.x * 0.92, 0.012, 0.045)
		marking.position = Vector3(road_position.x, 0.105, road_position.z + offset)
	else:
		mesh.size = Vector3(0.045, 0.012, road_size.z * 0.92)
		marking.position = Vector3(road_position.x + offset, 0.105, road_position.z)
	marking.mesh = mesh
	marking.rotation.y = road_rotation_y
	marking.set_surface_override_material(0, _material(Color(0.92, 0.88, 0.52)))
	_mark_generated(marking)
	add_child(marking)


func _add_intersection_marker(center: Vector3, radius: float) -> void:
	var marker := MeshInstance3D.new()
	marker.name = "CentralIntersection_Surface"
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = 0.1
	mesh.radial_segments = 32
	marker.mesh = mesh
	marker.position = Vector3(center.x, 0.11, center.z)
	marker.set_surface_override_material(0, _material(Color(0.05, 0.05, 0.055)))
	_mark_generated(marker)
	add_child(marker)
	intersection_count += 1


func _add_zones() -> void:
	var factory = ZoneVisualFactoryScript.new()
	factory.configure(zone_catalog_path)
	_add_zone(factory, "Z_RES", "residential", "Khu dân cư", Vector3(-10.5, 0.18, -10.5), 1.45)
	_add_zone(factory, "Z_HOSP", "hospital", "Bệnh viện", Vector3(10.5, 0.18, -10.5), 1.45)
	_add_zone(factory, "Z_IND", "industrial", "Khu công nghiệp", Vector3(-10.5, 0.18, 10.5), 1.45)
	_add_zone(factory, "Z_COM", "commercial", "Thương mại", Vector3(10.5, 0.18, 10.5), 1.45)


func _add_zone(factory, zone_id: String, zone_type: String, display_name: String, zone_position: Vector3, visual_scale: float) -> void:
	var zone_data := {
		"id": zone_id,
		"type": zone_type,
		"name": display_name,
	}
	var zone = factory.create_zone(zone_data)
	if not (zone is Node3D):
		return
	var zone_node := zone as Node3D
	zone_node.position = zone_position
	zone_node.scale = Vector3.ONE * visual_scale
	_mark_generated(zone_node)
	add_child(zone_node)
	spawned_zone_count += 1


func _add_sample_vehicles() -> void:
	var catalog = load(vehicle_catalog_path)
	if catalog == null or not catalog.has_method("scene_for_vehicle_type"):
		return
	_add_vehicle(catalog, "PRIVATE_CAR", Vector3(-5.8, 0.32, -0.9), 90.0, 0.75)
	_add_vehicle(catalog, "BUS", Vector3(0.9, 0.35, 5.8), 0.0, 0.95)
	_add_vehicle(catalog, "AMBULANCE", Vector3(6.2, 0.34, 0.9), -90.0, 0.8)
	_add_vehicle(catalog, "HEAVY_TRUCK", Vector3(-0.9, 0.35, -6.0), 180.0, 0.9)


func _add_vehicle(catalog, vehicle_type: String, vehicle_position: Vector3, yaw_degrees: float, visual_scale: float) -> void:
	var scene = catalog.scene_for_vehicle_type(vehicle_type)
	if not (scene is PackedScene):
		return
	var instance = (scene as PackedScene).instantiate()
	if not (instance is Node3D):
		if instance != null:
			instance.queue_free()
		return
	var vehicle := instance as Node3D
	vehicle.name = "PreviewVehicle_%s" % vehicle_type
	vehicle.position = vehicle_position
	vehicle.rotation_degrees.y = yaw_degrees
	vehicle.scale *= visual_scale
	_mark_generated(vehicle)
	add_child(vehicle)
	spawned_vehicle_count += 1


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("tiny_zone_preview_generated"):
			child.queue_free()
	spawned_zone_count = 0
	spawned_vehicle_count = 0
	road_count = 0
	intersection_count = 0


func _mark_generated(node: Node) -> void:
	node.add_to_group("tiny_zone_preview_generated")


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	return material


func _count_building_visuals() -> int:
	var total := 0
	for child in get_children():
		if not child.is_in_group("tiny_zone_preview_generated"):
			continue
		var cluster := child.get_node_or_null("BuildingClusterRoot")
		if cluster != null:
			total += cluster.get_child_count()
	return total
