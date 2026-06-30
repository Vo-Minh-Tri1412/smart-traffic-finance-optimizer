@tool
class_name DestinationPoint
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var destination_id := ""
@export var zone_id := ""
@export var display_name := ""


func _ready() -> void:
	_register_authoring_marker("authoring_destination")


func to_authoring_dict(_context: Dictionary = {}) -> Dictionary:
	return {
		"id": destination_id,
		"zone_id": zone_id,
		"name": display_name_or(destination_id, display_name),
	}
