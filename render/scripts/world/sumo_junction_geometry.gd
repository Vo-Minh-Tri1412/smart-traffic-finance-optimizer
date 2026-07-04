class_name SumoJunctionGeometry
extends RefCounted

var junction_id := ""
var junction_type := ""
var point := Vector2.ZERO
var shape_points: Array[Vector2] = []


func configure(id: String, position_m: Vector2, shape: Array[Vector2] = [], type_value := "") -> void:
	junction_id = id
	junction_type = type_value
	point = position_m
	shape_points = shape.duplicate()


func is_valid() -> bool:
	return not junction_id.is_empty()


func is_traffic_light() -> bool:
	return junction_type == "traffic_light"
