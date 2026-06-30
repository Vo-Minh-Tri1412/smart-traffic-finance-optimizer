class_name SumoJunctionGeometry
extends RefCounted

var junction_id := ""
var point := Vector2.ZERO


func configure(id: String, position_m: Vector2) -> void:
	junction_id = id
	point = position_m


func is_valid() -> bool:
	return not junction_id.is_empty()
