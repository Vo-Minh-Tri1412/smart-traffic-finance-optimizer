class_name VehicleBase
extends Node3D

@onready var body: MeshInstance3D = $Body

@export var default_vehicle_type := "UNKNOWN"
@export var visual_scale := Vector3(0.68, 0.62, 1.2)
@export var visual_color := Color(0.70, 0.70, 0.70)
@export var body_height := 0.25

var vehicle_id := ""
var vehicle_type := default_vehicle_type


func configure(type_id: String, id: String = "") -> void:
	vehicle_type = type_id
	vehicle_id = id
	name = _safe_node_name(id if not id.is_empty() else type_id)
	_apply_visual_style()


func _ready() -> void:
	if vehicle_type == "UNKNOWN" and default_vehicle_type != "UNKNOWN":
		vehicle_type = default_vehicle_type
	_apply_visual_style()


func apply_trace_vehicle(vehicle, mapper) -> void:
	var x := float(_vehicle_value(vehicle, "x", 0.0))
	var y := float(_vehicle_value(vehicle, "y", 0.0))
	var angle := float(_vehicle_value(vehicle, "angle", 0.0))
	position = mapper.sumo_to_world(x, y, body_height)
	rotation.y = mapper.sumo_angle_to_yaw(angle)


func _apply_visual_style() -> void:
	scale = visual_scale
	if body == null:
		return
	var material := StandardMaterial3D.new()
	material.albedo_color = visual_color
	body.set_surface_override_material(0, material)


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_")


func _vehicle_value(vehicle, key: String, fallback):
	if vehicle is Dictionary:
		return (vehicle as Dictionary).get(key, fallback)
	if vehicle is Object:
		var value = (vehicle as Object).get(key)
		return fallback if value == null else value
	return fallback
