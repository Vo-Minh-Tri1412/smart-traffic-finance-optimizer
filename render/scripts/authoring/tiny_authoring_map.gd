@tool
class_name TinyAuthoringMap
extends Node3D

const VehicleFactoryScript := preload("res://scripts/assets/vehicle_factory.gd")

@export var build_roads_on_ready := true
@export var rebuild_roads := false:
	set(value):
		rebuild_roads = false
		if is_inside_tree():
			rebuild_roads_preview()

@export_group("Commute Preview")
@export var enable_commute_preview := true:
	set(value):
		enable_commute_preview = value
		set_process(enable_commute_preview)
		if not is_inside_tree():
			return
		if enable_commute_preview:
			call_deferred("rebuild_commute_preview")
		else:
			_clear_commute_preview()
@export var commute_origin_zone_id := "Z_RES"
@export var commute_destination_zone_id := "Z_IND"
@export var commute_vehicle_catalog_path := "res://resources/catalogs/VehicleAssetCatalog.tres"
@export var commute_vehicle_types := PackedStringArray(["PRIVATE_CAR", "MOTORBIKE", "WORKER_SHUTTLE", "LIGHT_TRUCK"])
@export_range(0, 48, 1) var commute_vehicle_count := 10
@export var commute_vehicle_speed_units_per_second := 3.2
@export_range(0.1, 2.0, 0.05) var commute_vehicle_scale_multiplier := 0.45
@export var commute_vehicle_lane_height := 0.34
@export var commute_lane_offsets := PackedFloat32Array([-0.48, 0.48])
@export var commute_route_corridor_x_values := PackedFloat32Array([-11.5, 0.0, 11.5])
@export var commute_route_corridor_z_values := PackedFloat32Array([-11.5, 0.0])
@export var refresh_commute_preview := false:
	set(value):
		refresh_commute_preview = false
		if is_inside_tree():
			call_deferred("rebuild_commute_preview")

var road_count := 0
var _commute_root: Node3D = null
var _commute_factory = null
var _commute_vehicles: Array = []
var _commute_elapsed_seconds := 0.0
var _commute_route_length := 0.0


func _ready() -> void:
	if build_roads_on_ready:
		call_deferred("rebuild_roads_preview")
	set_process(enable_commute_preview)
	if enable_commute_preview:
		call_deferred("rebuild_commute_preview")


func _process(delta: float) -> void:
	if not enable_commute_preview:
		return
	if _commute_vehicles.is_empty():
		return
	_commute_elapsed_seconds += delta
	_update_commute_vehicles()


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
		"commute_vehicle_preview_count": _commute_vehicles.size(),
		"commute_route_length": _commute_route_length,
		"commute_lane_offset_count": commute_lane_offsets.size(),
		"commute_vehicle_scale_multiplier": commute_vehicle_scale_multiplier,
	}


func rebuild_commute_preview() -> void:
	_clear_commute_preview()
	if not enable_commute_preview or commute_vehicle_count <= 0:
		return

	var origin_zone := _zone_by_id(commute_origin_zone_id)
	var destination_zone := _zone_by_id(commute_destination_zone_id)
	if origin_zone == null or destination_zone == null:
		push_warning(
			"Cannot build commute preview. Missing origin=%s or destination=%s zone."
			% [commute_origin_zone_id, commute_destination_zone_id]
		)
		return

	var route := _commute_route_points(origin_zone as Node3D, destination_zone as Node3D)
	_commute_route_length = _route_length(route)
	if route.size() < 2 or _commute_route_length <= 0.01:
		push_warning("Cannot build commute preview. Route is too short.")
		return

	_commute_root = Node3D.new()
	_commute_root.name = "GeneratedCommutePreviewVehicles"
	_commute_root.add_to_group("tiny_authoring_generated_commute_preview")
	add_child(_commute_root)

	_commute_factory = VehicleFactoryScript.new()
	var catalog_loaded: bool = _commute_factory.configure(commute_vehicle_catalog_path)
	if not catalog_loaded:
		push_warning("Vehicle catalog failed to load; commute preview will use fallback boxes.")

	_commute_elapsed_seconds = 0.0
	var vehicle_types := _commute_vehicle_type_list()
	for index in range(commute_vehicle_count):
		var vehicle_type := String(vehicle_types[index % vehicle_types.size()])
		var vehicle: Node3D = _commute_factory.create_vehicle(
			vehicle_type,
			"commute_%02d_%s" % [index + 1, vehicle_type]
		)
		if vehicle == null:
			vehicle = _placeholder_vehicle(vehicle_type, index)
		if vehicle == null:
			continue
		vehicle.scale *= commute_vehicle_scale_multiplier
		_commute_root.add_child(vehicle)
		_commute_vehicles.append(
			{
				"node": vehicle,
				"route": route,
				"offset": _commute_route_length * float(index) / float(max(1, commute_vehicle_count)),
				"lane_offset": _lane_offset_for_vehicle(index),
				"speed": commute_vehicle_speed_units_per_second,
			}
		)
	_update_commute_vehicles()


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


func _clear_commute_preview() -> void:
	for child in get_children():
		if child.is_in_group("tiny_authoring_generated_commute_preview"):
			child.queue_free()
	_commute_root = null
	_commute_factory = null
	_commute_vehicles.clear()
	_commute_elapsed_seconds = 0.0
	_commute_route_length = 0.0


func _mark_generated(node: Node) -> void:
	node.add_to_group("tiny_authoring_generated_roads")


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	return material


func _zone_by_id(zone_id: String) -> Node:
	for zone in get_tree().get_nodes_in_group("zone_lot_authoring"):
		if not (zone is Node):
			continue
		var zone_node := zone as Node
		if not is_ancestor_of(zone_node):
			continue
		if str(zone_node.get("zone_id")) == zone_id:
			return zone_node
	return null


func _commute_vehicle_type_list() -> PackedStringArray:
	if commute_vehicle_types.is_empty():
		return PackedStringArray(["PRIVATE_CAR"])
	return commute_vehicle_types


func _commute_route_points(origin_zone: Node3D, destination_zone: Node3D) -> Array:
	var origin := to_local(origin_zone.global_position)
	var destination := to_local(destination_zone.global_position)
	var origin_access := _nearest_road_access(origin)
	var destination_access := _nearest_road_access(destination)
	var y := commute_vehicle_lane_height
	var points: Array = [
		Vector3(origin.x, y, origin.z),
		Vector3(float(origin_access.get("x", origin.x)), y, float(origin_access.get("z", origin.z))),
	]
	points.append_array(_road_path_between_access_points(origin_access, destination_access, y))
	points.append(Vector3(float(destination_access.get("x", destination.x)), y, float(destination_access.get("z", destination.z))))
	points.append(Vector3(destination.x, y, destination.z))
	return _dedupe_route_points(points)


func _nearest_vertical_corridor(target_x: float) -> float:
	if commute_route_corridor_x_values.is_empty():
		return 0.0
	var best_value := float(commute_route_corridor_x_values[0])
	var best_distance: float = abs(target_x - best_value)
	for value in commute_route_corridor_x_values:
		var distance: float = abs(target_x - float(value))
		if distance < best_distance:
			best_distance = distance
			best_value = float(value)
	return best_value


func _nearest_horizontal_corridor(target_z: float) -> float:
	if commute_route_corridor_z_values.is_empty():
		return 0.0
	var best_value := float(commute_route_corridor_z_values[0])
	var best_distance: float = abs(target_z - best_value)
	for value in commute_route_corridor_z_values:
		var distance: float = abs(target_z - float(value))
		if distance < best_distance:
			best_distance = distance
			best_value = float(value)
	return best_value


func _nearest_road_access(point: Vector3) -> Dictionary:
	var best := {
		"kind": "vertical",
		"x": point.x,
		"z": point.z,
		"distance": INF,
	}
	for corridor_x in commute_route_corridor_x_values:
		var x_value := float(corridor_x)
		var distance_x: float = abs(point.x - x_value)
		if distance_x < float(best["distance"]):
			best = {
				"kind": "vertical",
				"x": x_value,
				"z": point.z,
				"distance": distance_x,
			}
	for corridor_z in commute_route_corridor_z_values:
		var z_value := float(corridor_z)
		var distance_z: float = abs(point.z - z_value)
		if distance_z < float(best["distance"]):
			best = {
				"kind": "horizontal",
				"x": point.x,
				"z": z_value,
				"distance": distance_z,
			}
	return best


func _road_path_between_access_points(origin_access: Dictionary, destination_access: Dictionary, y: float) -> Array:
	var origin_kind := String(origin_access.get("kind", "vertical"))
	var destination_kind := String(destination_access.get("kind", "vertical"))
	var origin_x := float(origin_access.get("x", 0.0))
	var origin_z := float(origin_access.get("z", 0.0))
	var destination_x := float(destination_access.get("x", 0.0))
	var destination_z := float(destination_access.get("z", 0.0))
	var points: Array = []

	if origin_kind == "vertical" and destination_kind == "horizontal":
		points.append(Vector3(origin_x, y, destination_z))
	elif origin_kind == "horizontal" and destination_kind == "vertical":
		points.append(Vector3(destination_x, y, origin_z))
	elif origin_kind == "vertical" and destination_kind == "vertical":
		if is_equal_approx(origin_x, destination_x):
			return points
		var bridge_z := _nearest_horizontal_corridor((origin_z + destination_z) * 0.5)
		points.append(Vector3(origin_x, y, bridge_z))
		points.append(Vector3(destination_x, y, bridge_z))
	elif origin_kind == "horizontal" and destination_kind == "horizontal":
		if is_equal_approx(origin_z, destination_z):
			return points
		var bridge_x := _nearest_vertical_corridor((origin_x + destination_x) * 0.5)
		points.append(Vector3(bridge_x, y, origin_z))
		points.append(Vector3(bridge_x, y, destination_z))
	return points


func _dedupe_route_points(points: Array) -> Array:
	var result: Array = []
	for point in points:
		var candidate := point as Vector3
		if result.is_empty() or (result[-1] as Vector3).distance_to(candidate) > 0.1:
			result.append(candidate)
	return result


func _route_length(route: Array) -> float:
	var length := 0.0
	for index in range(route.size() - 1):
		length += (route[index] as Vector3).distance_to(route[index + 1] as Vector3)
	return length


func _update_commute_vehicles() -> void:
	if _commute_route_length <= 0.0:
		return
	for vehicle_entry in _commute_vehicles:
		var entry := vehicle_entry as Dictionary
		var node := entry.get("node") as Node3D
		if node == null or not is_instance_valid(node):
			continue
		var route := entry.get("route", []) as Array
		var speed := float(entry.get("speed", commute_vehicle_speed_units_per_second))
		var offset := float(entry.get("offset", 0.0))
		var lane_offset := float(entry.get("lane_offset", 0.0))
		var distance := fposmod(offset + _commute_elapsed_seconds * speed, _commute_route_length)
		var sample := _sample_route(route, distance, lane_offset)
		node.position = sample.get("position", Vector3.ZERO)
		var direction := sample.get("direction", Vector3.FORWARD) as Vector3
		if direction.length() > 0.01:
			node.rotation.y = atan2(direction.x, direction.z)


func _sample_route(route: Array, distance: float, lane_offset: float = 0.0) -> Dictionary:
	var remaining := distance
	for index in range(route.size() - 1):
		var start := route[index] as Vector3
		var end := route[index + 1] as Vector3
		var segment := end - start
		var segment_length := segment.length()
		if segment_length <= 0.001:
			continue
		if remaining <= segment_length:
			var amount := remaining / segment_length
			var direction := segment.normalized()
			return {
				"position": start.lerp(end, amount) + _lane_offset_vector(direction, lane_offset),
				"direction": direction,
			}
		remaining -= segment_length
	var fallback_start := route[max(0, route.size() - 2)] as Vector3
	var fallback_end := route[max(0, route.size() - 1)] as Vector3
	var fallback_direction := (fallback_end - fallback_start).normalized()
	return {
		"position": fallback_end + _lane_offset_vector(fallback_direction, lane_offset),
		"direction": fallback_direction,
	}


func _lane_offset_for_vehicle(index: int) -> float:
	if commute_lane_offsets.is_empty():
		return 0.0
	return float(commute_lane_offsets[index % commute_lane_offsets.size()])


func _lane_offset_vector(direction: Vector3, lane_offset: float) -> Vector3:
	if abs(lane_offset) <= 0.001 or direction.length() <= 0.001:
		return Vector3.ZERO
	var normal := Vector3(-direction.z, 0.0, direction.x).normalized()
	return normal * lane_offset


func _placeholder_vehicle(vehicle_type: String, index: int) -> Node3D:
	var body := MeshInstance3D.new()
	body.name = "CommutePreview_%02d_%s" % [index + 1, vehicle_type]
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.55, 0.30, 0.95)
	body.mesh = mesh
	body.set_surface_override_material(0, _material(_placeholder_vehicle_color(vehicle_type)))
	return body


func _placeholder_vehicle_color(vehicle_type: String) -> Color:
	match vehicle_type.to_upper():
		"MOTORBIKE", "DELIVERY_BIKE":
			return Color(0.18, 0.55, 1.0, 1.0)
		"WORKER_SHUTTLE", "BUS", "SCHOOL_BUS":
			return Color(1.0, 0.82, 0.15, 1.0)
		"LIGHT_TRUCK", "HEAVY_TRUCK":
			return Color(0.62, 0.36, 0.18, 1.0)
		_:
			return Color(0.1, 0.35, 0.95, 1.0)
