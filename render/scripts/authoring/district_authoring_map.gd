@tool
class_name DistrictAuthoringMap
extends Node3D

@export var district_id := "godot_authoring_district_v1"
@export var display_name := "Godot Authored District V1"
@export var version := "0.1.0"
@export var horizon_seconds := 3600
@export var time_step_seconds := 1


func _ready() -> void:
	add_to_group("authoring_district")


func authoring_metadata(overrides: Dictionary = {}) -> Dictionary:
	return {
		"id": String(overrides.get("district_id", district_id)),
		"name": String(overrides.get("district_name", display_name)),
		"version": String(overrides.get("version", version)),
		"horizon_seconds": int(overrides.get("horizon_seconds", horizon_seconds)),
		"time_step_seconds": int(overrides.get("time_step_seconds", time_step_seconds)),
	}
