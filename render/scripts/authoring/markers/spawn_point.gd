@tool
class_name SpawnPoint
extends Node3D

@export var spawn_id := ""
@export var flow_id := ""
@export var origin_zone := ""
@export var destination_zone := ""
@export var trip_purpose := ""
@export var departure_start := 0
@export var departure_end := 3600
@export var base_volume := 60
@export var route_policy := "SHORTEST_TIME"
@export var vehicle_mix: Dictionary = {"MOTORBIKE": 0.6, "CAR": 0.4}


func _ready() -> void:
	add_to_group("authoring_spawn")
