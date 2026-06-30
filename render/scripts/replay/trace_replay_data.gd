class_name TraceReplayData
extends RefCounted

const TraceFrameDataScript := preload("res://scripts/replay/trace_frame_data.gd")

var frames: Array = []
var errors: Array[String] = []
var unique_vehicle_ids: Dictionary = {}
var schema_version := ""
var bounds_min := Vector2.ZERO
var bounds_max := Vector2.ZERO
var _has_bounds := false


func load_jsonl(path: String, max_frames: int = 0) -> bool:
	frames.clear()
	errors.clear()
	unique_vehicle_ids.clear()
	schema_version = ""
	_has_bounds = false

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		errors.append("Cannot open trace file: %s" % path)
		return false

	var line_number := 0
	while not file.eof_reached():
		var line := file.get_line().strip_edges()
		line_number += 1
		if line.is_empty():
			continue

		var parsed = JSON.parse_string(line)
		if typeof(parsed) != TYPE_DICTIONARY:
			errors.append("Line %d is not a JSON object." % line_number)
			continue

		var frame = TraceFrameDataScript.new()
		if not frame.populate_from_dictionary(parsed as Dictionary, line_number, errors):
			continue

		frames.append(frame)
		if schema_version.is_empty():
			schema_version = String(frame.schema_version)
		_update_bounds(frame)
		if max_frames > 0 and frames.size() >= max_frames:
			break

	file.close()
	if frames.is_empty():
		errors.append("Trace file contained no valid vehicle-level frames.")
		return false
	return errors.is_empty()


func loaded_frame_count() -> int:
	return frames.size()


func unique_vehicle_count() -> int:
	return unique_vehicle_ids.size()


func has_bounds() -> bool:
	return _has_bounds


func _update_bounds(frame) -> void:
	for vehicle in frame.vehicles:
		var x := float(vehicle.x)
		var y := float(vehicle.y)
		unique_vehicle_ids[String(vehicle.vehicle_id)] = true
		if not _has_bounds:
			bounds_min = Vector2(x, y)
			bounds_max = Vector2(x, y)
			_has_bounds = true
		else:
			bounds_min.x = min(bounds_min.x, x)
			bounds_min.y = min(bounds_min.y, y)
			bounds_max.x = max(bounds_max.x, x)
			bounds_max.y = max(bounds_max.y, y)
