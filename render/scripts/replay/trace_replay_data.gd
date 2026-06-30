class_name TraceReplayData
extends RefCounted

var frames: Array = []
var errors: Array[String] = []
var unique_vehicle_ids: Dictionary = {}
var bounds_min := Vector2.ZERO
var bounds_max := Vector2.ZERO
var _has_bounds := false


func load_jsonl(path: String, max_frames: int = 0) -> bool:
	frames.clear()
	errors.clear()
	unique_vehicle_ids.clear()
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

		var frame := parsed as Dictionary
		if not _validate_frame(frame, line_number):
			continue

		frames.append(frame)
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


func _validate_frame(frame: Dictionary, line_number: int) -> bool:
	var required := ["timestep", "time_seconds", "district_id", "scenario_id", "controller_id", "engine_id", "vehicles"]
	for key in required:
		if not frame.has(key):
			errors.append("Line %d missing required key: %s" % [line_number, key])
			return false
	if typeof(frame["vehicles"]) != TYPE_ARRAY:
		errors.append("Line %d has non-array vehicles field." % line_number)
		return false
	for vehicle in frame["vehicles"]:
		if typeof(vehicle) != TYPE_DICTIONARY:
			errors.append("Line %d has a non-object vehicle entry." % line_number)
			return false
		var vehicle_dict := vehicle as Dictionary
		for key in ["vehicle_id", "vehicle_type", "x", "y", "speed", "angle"]:
			if not vehicle_dict.has(key):
				errors.append("Line %d vehicle missing required key: %s" % [line_number, key])
				return false
	return true


func _update_bounds(frame: Dictionary) -> void:
	for vehicle in frame.get("vehicles", []):
		var vehicle_dict := vehicle as Dictionary
		var x := float(vehicle_dict.get("x", 0.0))
		var y := float(vehicle_dict.get("y", 0.0))
		unique_vehicle_ids[String(vehicle_dict.get("vehicle_id", ""))] = true
		if not _has_bounds:
			bounds_min = Vector2(x, y)
			bounds_max = Vector2(x, y)
			_has_bounds = true
		else:
			bounds_min.x = min(bounds_min.x, x)
			bounds_min.y = min(bounds_min.y, y)
			bounds_max.x = max(bounds_max.x, x)
			bounds_max.y = max(bounds_max.y, y)
