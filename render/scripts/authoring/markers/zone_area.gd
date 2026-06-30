@tool
class_name ZoneArea
extends Node3D

@export var zone_id := ""
@export var display_name := ""
@export var zone_type := "mixed"
@export var intersection_ids: Array[String] = []
@export var economic_role := ""
@export var peak_windows: Array[String] = []


func _ready() -> void:
	add_to_group("authoring_zone")
