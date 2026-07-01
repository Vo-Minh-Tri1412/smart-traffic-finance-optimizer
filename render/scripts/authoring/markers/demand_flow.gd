@tool
class_name DemandFlow
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var flow_id := ""
@export_node_path("Node3D") var origin_zone_path: NodePath = NodePath("")
@export var origin_zone := ""
@export_node_path("Node3D") var destination_zone_path: NodePath = NodePath("")
@export var destination_zone := ""
@export var trip_purpose := ""
@export var departure_start := 0
@export var departure_end := 3600
@export var base_volume := 60
@export_enum(
	"SHORTEST_TIME",
	"CONGESTION_AWARE",
	"FIXED_ROUTE",
	"TRUCK_LEGAL_ROUTE",
	"PRIORITY_FASTEST",
)
var route_policy := "SHORTEST_TIME"
@export var vehicle_mix: Dictionary = {"MOTORBIKE": 0.6, "CAR": 0.4}


func _ready() -> void:
	_register_authoring_marker("authoring_demand_flow")
	# Compatibility group for older exporter/tests that still describe flows as spawns.
	add_to_group("authoring_spawn")


func to_authoring_dict(_context: Dictionary = {}) -> Dictionary:
	var resolved_origin_zone := node_id_from_path(origin_zone_path, "zone_id")
	if resolved_origin_zone.is_empty():
		resolved_origin_zone = origin_zone
	var resolved_destination_zone := node_id_from_path(destination_zone_path, "zone_id")
	if resolved_destination_zone.is_empty():
		resolved_destination_zone = destination_zone
	return {
		"id": flow_id,
		"origin_zone": resolved_origin_zone,
		"destination_zone": resolved_destination_zone,
		"trip_purpose": trip_purpose,
		"departure_start": departure_start,
		"departure_end": departure_end,
		"base_volume": base_volume,
		"vehicle_mix": normalized_number_map(vehicle_mix, {"MOTORBIKE": 0.6, "CAR": 0.4}),
		"route_policy": route_policy,
	}
