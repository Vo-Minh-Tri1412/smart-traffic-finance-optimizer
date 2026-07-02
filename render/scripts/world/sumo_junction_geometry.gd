class_name SumoJunctionGeometry
extends RefCounted

var junction_id := ""
var point := Vector2.ZERO
var shape_points: Array[Vector2] = []


func configure(id: String, position_m: Vector2, shape: Array[Vector2] = []) -> void:
	junction_id = id
	point = position_m
	shape_points = shape.duplicate()


func is_valid() -> bool:
	return not junction_id.is_empty()
