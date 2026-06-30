@tool
class_name TrafficLightMarker
extends Node3D

@export var intersection_id := ""
@export var program_hint := "fixed_time"
@export var notes := ""


func _ready() -> void:
	add_to_group("authoring_traffic_light")
