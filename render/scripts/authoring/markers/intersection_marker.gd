@tool
class_name IntersectionMarker
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var intersection_id := ""
@export var display_name := ""
@export var signalized := true
@export var tags: Array[String] = []


func _ready() -> void:
	_register_authoring_marker("authoring_intersection")


func to_authoring_dict(context: Dictionary = {}) -> Dictionary:
	var traffic_light_ids := context.get("traffic_light_ids", {}) as Dictionary
	var point := global_position_km()
	return {
		"id": intersection_id,
		"name": display_name_or(intersection_id, display_name),
		"x": point.x,
		"y": point.y,
		"tags": string_array(tags),
		"signalized": signalized or traffic_light_ids.has(intersection_id),
	}
