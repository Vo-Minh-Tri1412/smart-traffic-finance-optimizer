@tool
class_name TrafficLightMarker
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export_node_path("Node3D") var intersection_path: NodePath = NodePath("")
@export var intersection_id := ""
@export var program_hint := "fixed_time"
@export var notes := ""


func _ready() -> void:
	_register_authoring_marker("authoring_traffic_light")


func to_authoring_dict(_context: Dictionary = {}) -> Dictionary:
	var resolved_intersection_id := node_id_from_path(intersection_path, "intersection_id")
	if resolved_intersection_id.is_empty():
		resolved_intersection_id = intersection_id
	return {
		"intersection_id": resolved_intersection_id,
		"program_hint": program_hint,
		"notes": notes,
	}
