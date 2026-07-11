@tool
class_name VehicleBase
extends Node3D

@onready var body: MeshInstance3D = $Body
@onready var physical_proxy: MeshInstance3D = $PhysicalProxy

@export var default_vehicle_type := "UNKNOWN"
@export var visual_scale := Vector3(0.68, 0.62, 1.2):
	set(value):
		visual_scale = value
		_request_visual_refresh()
@export var visual_color := Color(0.70, 0.70, 0.70):
	set(value):
		visual_color = value
		_request_visual_refresh()
@export var body_height := 0.25:
	set(value):
		body_height = value
		_request_visual_refresh()

@export_group("Canonical Physical Geometry")
@export var physical_dimensions_m := Vector3(1.8, 1.5, 4.5)
@export var physical_ground_clearance_m := 0.0

@export_group("Scene Visual Asset")
@export var visual_asset_scene: PackedScene:
	set(value):
		visual_asset_scene = value
		_request_visual_refresh()
@export var visual_asset_scale := Vector3.ONE:
	set(value):
		visual_asset_scale = value
		_request_visual_refresh()
@export var visual_asset_offset := Vector3.ZERO:
	set(value):
		visual_asset_offset = value
		_request_visual_refresh()
@export var visual_asset_rotation_degrees := Vector3.ZERO:
	set(value):
		visual_asset_rotation_degrees = value
		_request_visual_refresh()
@export var visual_asset_override_material: Material:
	set(value):
		visual_asset_override_material = value
		_request_visual_refresh()
@export var hide_body_when_visual_asset_exists := true:
	set(value):
		hide_body_when_visual_asset_exists = value
		_request_visual_refresh()
@export var fit_visual_asset_to_physical_proxy := true:
	set(value):
		fit_visual_asset_to_physical_proxy = value
		_request_visual_refresh()
@export var rebuild_asset_preview := false:
	set(value):
		rebuild_asset_preview = false
		_request_visual_refresh()

var vehicle_id := ""
var vehicle_type := default_vehicle_type
var trace_lateral_position_m := 0.0
var _has_trace_physical_geometry := false
var _last_trace_world_scale := 1.0


func configure(type_id: String, id: String = "") -> void:
	vehicle_type = type_id
	vehicle_id = id
	name = _safe_node_name(id if not id.is_empty() else type_id)
	_refresh_visual_asset()


func _ready() -> void:
	add_to_group("sensor_target_vehicle")
	if vehicle_type == "UNKNOWN" and default_vehicle_type != "UNKNOWN":
		vehicle_type = default_vehicle_type
	_refresh_visual_asset()


func apply_trace_vehicle(vehicle, mapper, geometry_world = null) -> void:
	var x := float(_vehicle_value(vehicle, "x", 0.0))
	var y := float(_vehicle_value(vehicle, "y", 0.0))
	var angle := float(_vehicle_value(vehicle, "angle", 0.0))
	var mapper_scale: float = 1.0
	if mapper != null and mapper.get("scale") != null:
		mapper_scale = float(mapper.get("scale"))
	var world_scale: float = max(0.0001, mapper_scale)
	var elevation_m := float(_vehicle_value(vehicle, "elevation_m", 0.0))
	var clearance_m := float(_vehicle_value(vehicle, "ground_clearance_m", body_height))
	trace_lateral_position_m = float(_vehicle_value(vehicle, "pos_lat_m", 0.0))
	var world_height := (elevation_m + clearance_m) * world_scale
	var mapped_position = null
	if geometry_world != null and geometry_world.has_method("world_position_for_trace_vehicle"):
		mapped_position = geometry_world.world_position_for_trace_vehicle(
			x,
			y,
			trace_lateral_position_m,
			world_height
		)
	if mapped_position is Vector3:
		position = mapped_position as Vector3
	elif mapper != null:
		position = mapper.sumo_to_world(x, y, world_height)
	else:
		position = Vector3(x * world_scale, world_height, y * world_scale)
	if mapper != null:
		rotation.y = mapper.sumo_angle_to_yaw(angle)
	_apply_trace_physical_geometry(vehicle, world_scale)


func _apply_trace_physical_geometry(vehicle, world_scale: float) -> void:
	var length_m := float(_vehicle_value(vehicle, "length_m", 0.0))
	var width_m := float(_vehicle_value(vehicle, "width_m", 0.0))
	var height_m := float(_vehicle_value(vehicle, "height_m", 0.0))
	var clearance_m := float(_vehicle_value(vehicle, "ground_clearance_m", 0.0))
	if min(length_m, min(width_m, height_m)) <= 0.0:
		return
	_has_trace_physical_geometry = true
	_last_trace_world_scale = world_scale
	physical_dimensions_m = Vector3(width_m, height_m, length_m)
	physical_ground_clearance_m = clearance_m
	_apply_physical_dimensions_to_body(world_scale)
	var proxy := _physical_proxy_node()
	if proxy != null:
		var mesh := proxy.mesh
		if mesh is BoxMesh:
			(mesh as BoxMesh).size = physical_dimensions_m * world_scale
		proxy.position = Vector3(0.0, physical_dimensions_m.y * world_scale / 2.0, 0.0)
	_fit_active_visual_asset_to_physical_proxy(world_scale)


func _apply_physical_dimensions_to_body(world_scale: float) -> void:
	var body_node := _body_node()
	if body_node == null:
		return
	var body_mesh := body_node.mesh
	if body_mesh is BoxMesh:
		(body_mesh as BoxMesh).size = physical_dimensions_m * world_scale
	body_node.scale = Vector3.ONE
	body_node.position = Vector3(0.0, physical_dimensions_m.y * world_scale / 2.0, 0.0)


func _physical_proxy_node() -> MeshInstance3D:
	if physical_proxy != null:
		return physical_proxy
	return get_node_or_null("PhysicalProxy") as MeshInstance3D


func _apply_visual_style() -> void:
	# VehicleBase stays at unit scale: the canonical PhysicalProxy must never inherit art scale.
	scale = Vector3.ONE
	var body_node := _body_node()
	if body_node == null:
		return
	if not _has_trace_physical_geometry:
		body_node.scale = visual_scale
	var material := StandardMaterial3D.new()
	material.albedo_color = visual_color
	body_node.set_surface_override_material(0, material)


func has_scene_visual_asset_configured() -> bool:
	return visual_asset_scene != null


func apply_external_visual_asset(
	asset_scene: PackedScene,
	asset_scale := Vector3.ONE,
	asset_offset := Vector3.ZERO,
	asset_rotation_degrees := Vector3.ZERO,
	hide_body := true
) -> bool:
	if visual_asset_scene != null:
		return false
	_spawn_visual_asset(
		asset_scene,
		asset_scale,
		asset_offset,
		asset_rotation_degrees,
		hide_body
	)
	return asset_scene != null


func _request_visual_refresh() -> void:
	if not is_inside_tree():
		return
	call_deferred("_refresh_visual_asset")


func _refresh_visual_asset() -> void:
	_apply_visual_style()
	_clear_generated_visual_asset()
	if visual_asset_scene == null:
		_set_body_visible(true)
		return
	_spawn_visual_asset(
		visual_asset_scene,
		visual_asset_scale,
		visual_asset_offset,
		visual_asset_rotation_degrees,
		hide_body_when_visual_asset_exists
	)


func _spawn_visual_asset(
	asset_scene: PackedScene,
	asset_scale: Vector3,
	asset_offset: Vector3,
	asset_rotation_degrees: Vector3,
	hide_body: bool
) -> void:
	if asset_scene == null:
		_set_body_visible(true)
		return
	var instance := asset_scene.instantiate()
	if not (instance is Node3D):
		if instance != null:
			instance.queue_free()
		push_warning("Vehicle visual asset for %s did not instantiate a Node3D." % vehicle_type)
		_set_body_visible(true)
		return
	var visual_root := Node3D.new()
	visual_root.name = "VisualAsset"
	visual_root.add_to_group("generated_vehicle_visual_asset")
	add_child(visual_root)
	var visual_asset := instance as Node3D
	visual_asset.name = "SourceAsset"
	visual_asset.scale = asset_scale
	visual_asset.position = asset_offset
	visual_asset.rotation_degrees = asset_rotation_degrees
	visual_root.add_child(visual_asset)
	if visual_asset_override_material != null:
		_apply_material_recursive(visual_root, visual_asset_override_material)
	if _has_trace_physical_geometry:
		_fit_active_visual_asset_to_physical_proxy(1.0)
	_set_body_visible(not hide_body)


func _clear_generated_visual_asset() -> void:
	var visual_asset := get_node_or_null("VisualAsset")
	if visual_asset == null:
		return
	remove_child(visual_asset)
	visual_asset.queue_free()


func _fit_active_visual_asset_to_physical_proxy(world_scale: float) -> void:
	if not fit_visual_asset_to_physical_proxy:
		return
	var visual_root := get_node_or_null("VisualAsset") as Node3D
	if visual_root == null:
		return
	# Reset before measuring so repeated replay frames never compound the fit scale.
	visual_root.position = Vector3.ZERO
	visual_root.scale = Vector3.ONE
	var bounds := _node_bounds_in_vehicle_space(visual_root)
	if not bool(bounds.get("valid", false)):
		push_warning("Vehicle visual asset for %s has no mesh bounds to fit." % vehicle_type)
		return
	var minimum := bounds.get("minimum", Vector3.ZERO) as Vector3
	var maximum := bounds.get("maximum", Vector3.ZERO) as Vector3
	var raw_size := maximum - minimum
	if min(raw_size.x, min(raw_size.y, raw_size.z)) <= 0.000001:
		push_warning("Vehicle visual asset for %s has degenerate mesh bounds." % vehicle_type)
		return
	var target_size := physical_dimensions_m * world_scale
	var fit_scale := Vector3(
		target_size.x / raw_size.x,
		target_size.y / raw_size.y,
		target_size.z / raw_size.z
	)
	visual_root.scale = fit_scale
	var target_minimum := Vector3(-target_size.x / 2.0, 0.0, -target_size.z / 2.0)
	visual_root.position = target_minimum - Vector3(
		minimum.x * fit_scale.x,
		minimum.y * fit_scale.y,
		minimum.z * fit_scale.z
	)


func visual_physical_fit_error_world_units() -> float:
	if not _has_trace_physical_geometry or not fit_visual_asset_to_physical_proxy:
		return -1.0
	var visual_root := get_node_or_null("VisualAsset") as Node3D
	if visual_root == null:
		return -1.0
	var bounds := _node_bounds_in_vehicle_space(visual_root)
	if not bool(bounds.get("valid", false)):
		return 1000000.0
	var minimum := bounds.get("minimum", Vector3.ZERO) as Vector3
	var maximum := bounds.get("maximum", Vector3.ZERO) as Vector3
	var target_size := physical_dimensions_m * _last_trace_world_scale
	var target_minimum := Vector3(-target_size.x / 2.0, 0.0, -target_size.z / 2.0)
	var target_maximum := target_minimum + target_size
	return max(
		max(abs(minimum.x - target_minimum.x), abs(minimum.y - target_minimum.y)),
		max(
			abs(minimum.z - target_minimum.z),
			max(abs(maximum.x - target_maximum.x), max(abs(maximum.y - target_maximum.y), abs(maximum.z - target_maximum.z)))
		)
	)


func _node_bounds_in_vehicle_space(root: Node3D) -> Dictionary:
	var bounds := {"valid": false, "minimum": Vector3.ZERO, "maximum": Vector3.ZERO}
	_collect_mesh_bounds(root, Transform3D.IDENTITY, bounds)
	return bounds


func _collect_mesh_bounds(node: Node, parent_transform: Transform3D, bounds: Dictionary) -> void:
	var local_transform := parent_transform
	if node is Node3D:
		local_transform = parent_transform * (node as Node3D).transform
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			_accumulate_aabb(mesh_instance.mesh.get_aabb(), local_transform, bounds)
	for child in node.get_children():
		_collect_mesh_bounds(child, local_transform, bounds)


func _accumulate_aabb(box: AABB, transform: Transform3D, bounds: Dictionary) -> void:
	for x_index in range(2):
		for y_index in range(2):
			for z_index in range(2):
				var corner := box.position + Vector3(
					box.size.x if x_index == 1 else 0.0,
					box.size.y if y_index == 1 else 0.0,
					box.size.z if z_index == 1 else 0.0
				)
				var point := transform * corner
				if not bool(bounds.get("valid", false)):
					bounds["valid"] = true
					bounds["minimum"] = point
					bounds["maximum"] = point
					continue
				var minimum := bounds.get("minimum", Vector3.ZERO) as Vector3
				var maximum := bounds.get("maximum", Vector3.ZERO) as Vector3
				bounds["minimum"] = minimum.min(point)
				bounds["maximum"] = maximum.max(point)


func _set_body_visible(is_visible: bool) -> void:
	var body_node := _body_node()
	if body_node != null:
		body_node.visible = is_visible


func _body_node() -> MeshInstance3D:
	if body != null:
		return body
	return get_node_or_null("Body") as MeshInstance3D


func _apply_material_recursive(node: Node, material: Material) -> void:
	if node is MeshInstance3D:
		(node as MeshInstance3D).set_surface_override_material(0, material)
	for child in node.get_children():
		_apply_material_recursive(child, material)


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_")


func _vehicle_value(vehicle, key: String, fallback):
	if vehicle is Dictionary:
		return (vehicle as Dictionary).get(key, fallback)
	if vehicle is Object:
		var value = (vehicle as Object).get(key)
		return fallback if value == null else value
	return fallback


func sensor_vehicle_id() -> String:
	return vehicle_id


func sensor_vehicle_type() -> String:
	return vehicle_type
