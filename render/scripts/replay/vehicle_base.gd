class_name VehicleBase
extends Node3D

@onready var body: MeshInstance3D = $Body

var vehicle_id := ""
var vehicle_type := "UNKNOWN"


func configure(type_id: String, id: String = "") -> void:
	vehicle_type = type_id
	vehicle_id = id
	name = _safe_node_name(id if not id.is_empty() else type_id)
	scale = _vehicle_scale(type_id)
	if body != null:
		var material := StandardMaterial3D.new()
		material.albedo_color = _vehicle_color(type_id)
		body.set_surface_override_material(0, material)


func apply_trace_vehicle(vehicle: Dictionary, mapper) -> void:
	var x := float(vehicle.get("x", 0.0))
	var y := float(vehicle.get("y", 0.0))
	var angle := float(vehicle.get("angle", 0.0))
	position = mapper.sumo_to_world(x, y, 0.25)
	rotation.y = mapper.sumo_angle_to_yaw(angle)


func _vehicle_scale(type_id: String) -> Vector3:
	match type_id:
		"MOTORBIKE", "DELIVERY_BIKE":
			return Vector3(0.45, 0.55, 0.75)
		"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE":
			return Vector3(0.9, 0.8, 2.1)
		"AMBULANCE":
			return Vector3(0.72, 0.7, 1.35)
		"LIGHT_TRUCK":
			return Vector3(0.85, 0.75, 1.6)
		"HEAVY_TRUCK":
			return Vector3(1.0, 0.85, 2.3)
		_:
			return Vector3(0.68, 0.62, 1.2)


func _vehicle_color(type_id: String) -> Color:
	match type_id:
		"MOTORBIKE", "DELIVERY_BIKE":
			return Color(0.12, 0.75, 0.22)
		"PRIVATE_CAR", "TAXI_RIDE_HAILING":
			return Color(0.12, 0.38, 0.90)
		"BUS", "SCHOOL_BUS", "WORKER_SHUTTLE":
			return Color(0.95, 0.78, 0.10)
		"AMBULANCE":
			return Color(0.95, 0.08, 0.08)
		"LIGHT_TRUCK", "HEAVY_TRUCK":
			return Color(0.70, 0.40, 0.18)
		_:
			return Color(0.70, 0.70, 0.70)


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_")
