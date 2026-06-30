@tool
class_name DestinationPoint
extends Node3D

@export var destination_id := ""
@export var zone_id := ""
@export var display_name := ""


func _ready() -> void:
	add_to_group("authoring_destination")
