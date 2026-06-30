@tool
class_name TrafficLightMarker
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var intersection_id := ""
@export var program_hint := "fixed_time"
@export var notes := ""


func _ready() -> void:
	_register_authoring_marker("authoring_traffic_light")


func to_authoring_dict(_context: Dictionary = {}) -> Dictionary:
	return {
		"intersection_id": intersection_id,
		"program_hint": program_hint,
		"notes": notes,
	}
