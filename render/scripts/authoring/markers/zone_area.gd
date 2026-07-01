@tool
class_name ZoneArea
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var zone_id := ""
@export var display_name := ""
@export var zone_type := "mixed"
@export var intersection_paths: Array[NodePath] = []
@export var intersection_ids: Array[String] = []
@export var economic_role := ""
@export var peak_windows: Array[String] = []


func _ready() -> void:
	_register_authoring_marker("authoring_zone")


func to_authoring_dict(_context: Dictionary = {}) -> Dictionary:
	var resolved_intersection_ids := ids_from_node_paths(intersection_paths, "intersection_id")
	if resolved_intersection_ids.is_empty():
		resolved_intersection_ids = string_array(intersection_ids)
	return {
		"id": zone_id,
		"name": display_name_or(zone_id, display_name),
		"type": zone_type,
		"intersection_ids": resolved_intersection_ids,
		"economic_role": economic_role,
		"peak_windows": string_array(peak_windows),
	}
