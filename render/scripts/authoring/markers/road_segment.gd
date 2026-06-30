@tool
class_name RoadSegment
extends Node3D

@export var road_id := ""
@export var from_intersection := ""
@export var to_intersection := ""
@export var bidirectional := true
@export var lanes := 2
@export var speed_kph := 40.0
@export var capacity := 900.0
@export var truck_allowed := true
@export var tags: Array[String] = []
@export var length_km_override := 0.0
@export var shape_points: PackedVector3Array = PackedVector3Array()


func _ready() -> void:
	add_to_group("authoring_road")
