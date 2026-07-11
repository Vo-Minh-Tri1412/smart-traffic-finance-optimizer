class_name CameraCalibrationLoader
extends RefCounted

const SCHEMA_VERSION := "camera_calibration.v1"


func load_entries(path: String, errors: Array[String]) -> Array:
	if path.is_empty():
		errors.append("Camera calibration path is empty.")
		return []
	if not FileAccess.file_exists(path):
		errors.append("Camera calibration file does not exist: %s" % path)
		return []
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		errors.append("Cannot open camera calibration file: %s" % path)
		return []
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		errors.append("Camera calibration root must be an object: %s" % path)
		return []
	var payload := parsed as Dictionary
	if String(payload.get("schema_version", "")) != SCHEMA_VERSION:
		errors.append("Unsupported camera calibration schema: %s" % path)
		return []
	var raw_entries = payload.get("cameras", [])
	if not (raw_entries is Array):
		errors.append("Camera calibration cameras must be an array: %s" % path)
		return []
	var entries: Array = []
	var ids: Dictionary = {}
	for raw_entry in raw_entries as Array:
		if not (raw_entry is Dictionary):
			errors.append("Camera calibration contains a non-object camera entry.")
			continue
		var entry := raw_entry as Dictionary
		var camera_id := String(entry.get("camera_id", "")).strip_edges()
		if camera_id.is_empty() or ids.has(camera_id):
			errors.append("Camera calibration has empty or duplicate camera_id: %s" % camera_id)
			continue
		if not _is_valid_entry(entry):
			errors.append("Camera calibration entry is missing physical fields: %s" % camera_id)
			continue
		ids[camera_id] = true
		entries.append(entry)
	return entries


func _is_valid_entry(entry: Dictionary) -> bool:
	var position = entry.get("position_m")
	var rotation = entry.get("rotation_degrees")
	var image_size = entry.get("image_size")
	var intrinsics = entry.get("intrinsics")
	return (
		position is Array
		and (position as Array).size() == 3
		and rotation is Dictionary
		and image_size is Dictionary
		and intrinsics is Dictionary
		and (image_size as Dictionary).has("width")
		and (image_size as Dictionary).has("height")
		and (intrinsics as Dictionary).has("fx")
		and (intrinsics as Dictionary).has("fy")
	)
