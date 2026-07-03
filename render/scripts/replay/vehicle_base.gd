@tool
class_name VehicleBase
extends Node3D

@onready var body: MeshInstance3D = $Body

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
@export var rebuild_asset_preview := false:
	set(value):
		rebuild_asset_preview = false
		_request_visual_refresh()

var vehicle_id := ""
var vehicle_type := default_vehicle_type


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


func apply_trace_vehicle(vehicle, mapper) -> void:
	var x := float(_vehicle_value(vehicle, "x", 0.0))
	var y := float(_vehicle_value(vehicle, "y", 0.0))
	var angle := float(_vehicle_value(vehicle, "angle", 0.0))
	position = mapper.sumo_to_world(x, y, body_height)
	rotation.y = mapper.sumo_angle_to_yaw(angle)


func _apply_visual_style() -> void:
	scale = visual_scale
	var body_node := _body_node()
	if body_node == null:
		return
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
	var visual_asset := instance as Node3D
	visual_asset.name = "VisualAsset"
	visual_asset.scale = asset_scale
	visual_asset.position = asset_offset
	visual_asset.rotation_degrees = asset_rotation_degrees
	visual_asset.add_to_group("generated_vehicle_visual_asset")
	if visual_asset_override_material != null:
		_apply_material_recursive(visual_asset, visual_asset_override_material)
	add_child(visual_asset)
	_set_body_visible(not hide_body)


func _clear_generated_visual_asset() -> void:
	var visual_asset := get_node_or_null("VisualAsset")
	if visual_asset == null:
		return
	remove_child(visual_asset)
	visual_asset.queue_free()


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
