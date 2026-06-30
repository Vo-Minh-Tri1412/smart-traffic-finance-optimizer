@tool
class_name IntersectionMarker
extends Node3D

@export var intersection_id := ""
@export var display_name := ""
@export var signalized := true
@export var tags: Array[String] = []


func _ready() -> void:
	add_to_group("authoring_intersection")
