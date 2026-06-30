@tool
class_name SpawnPoint
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var spawn_id := ""
@export var flow_id := ""
@export var origin_zone := ""
@export var destination_zone := ""
@export var trip_purpose := ""
@export var departure_start := 0
@export var departure_end := 3600
@export var base_volume := 60
@export var route_policy := "SHORTEST_TIME"
@export var vehicle_mix: Dictionary = {"MOTORBIKE": 0.6, "CAR": 0.4}


func _ready() -> void:
	_register_authoring_marker("authoring_spawn")


func to_authoring_dict(_context: Dictionary = {}) -> Dictionary:
	var actual_flow_id := flow_id
	if actual_flow_id.is_empty():
		actual_flow_id = spawn_id
	return {
		"id": actual_flow_id,
		"origin_zone": origin_zone,
		"destination_zone": destination_zone,
		"trip_purpose": trip_purpose,
		"departure_start": departure_start,
		"departure_end": departure_end,
		"base_volume": base_volume,
		"vehicle_mix": normalized_number_map(vehicle_mix, {"MOTORBIKE": 0.6, "CAR": 0.4}),
		"route_policy": route_policy,
	}
