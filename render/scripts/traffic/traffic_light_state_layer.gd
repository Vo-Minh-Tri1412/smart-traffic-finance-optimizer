class_name TrafficLightStateLayer
extends Node3D

const SchemaVersions := preload("res://scripts/contracts/schema_versions.gd")

@export var trace_path := ""
@export var auto_load := false

signal traffic_lights_updated(states: Dictionary)

var loaded_frame_count := 0
var traffic_light_sync_count := 0
var parse_error_count := 0
var traffic_light_ids: Dictionary = {}
var errors: Array[String] = []

var _frames: Array[Dictionary] = []
var _current_frame_index := -1


func _ready() -> void:
	if auto_load and not trace_path.is_empty():
		load_trace(trace_path)


func load_trace(path: String) -> bool:
	loaded_frame_count = 0
	traffic_light_sync_count = 0
	parse_error_count = 0
	traffic_light_ids.clear()
	errors.clear()
	_frames.clear()
	_current_frame_index = -1

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		errors.append("Traffic-light trace not found: %s" % path)
		return false

	while not file.eof_reached():
		var line := file.get_line().strip_edges()
		if line.is_empty():
			continue
		var parsed = JSON.parse_string(line)
		if not (parsed is Dictionary):
			parse_error_count += 1
			continue
		var frame := parsed as Dictionary
		if String(frame.get("schema_version", "")) != SchemaVersions.TRAFFIC_LIGHT_TRACE_SCHEMA_VERSION:
			parse_error_count += 1
			continue
		loaded_frame_count += 1
		var states = frame.get("traffic_lights", [])
		if not (states is Array):
			parse_error_count += 1
			continue
		
		var frame_data := {
			"time_seconds": float(frame.get("time_seconds", 0.0)),
			"states": {}
		}
		
		for item in states as Array:
			if not (item is Dictionary):
				parse_error_count += 1
				continue
			var state := item as Dictionary
			var traffic_light_id := String(state.get("traffic_light_id", ""))
			var state_val := String(state.get("state", ""))
			if traffic_light_id.is_empty():
				parse_error_count += 1
				continue
			traffic_light_ids[traffic_light_id] = true
			traffic_light_sync_count += 1
			frame_data.states[traffic_light_id] = state_val
		_frames.append(frame_data)
	file.close()
	return loaded_frame_count > 0 and parse_error_count == 0


func apply_time(time_seconds: float) -> void:
	if _frames.is_empty():
		return
	
	var target_idx := 0
	for i in range(_frames.size()):
		if _frames[i].time_seconds <= time_seconds:
			target_idx = i
		else:
			break
			
	if target_idx != _current_frame_index:
		_current_frame_index = target_idx
		traffic_lights_updated.emit(_frames[target_idx].states)



func summary() -> Dictionary:
	return {
		"traffic_light_trace_path": trace_path,
		"loaded_traffic_light_frames": loaded_frame_count,
		"traffic_light_sync_count": traffic_light_sync_count,
		"traffic_light_count": traffic_light_ids.size(),
		"traffic_light_parse_error_count": parse_error_count,
		"errors": errors,
	}
