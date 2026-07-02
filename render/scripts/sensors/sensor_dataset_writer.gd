class_name SensorDatasetWriter
extends RefCounted

var dataset_root := ""
var dataset_id := ""
var label_catalog = null
var render_manifest_frames: Array = []
var frame_manifest_file: FileAccess = null


func configure(root: String, id: String, catalog) -> bool:
	dataset_root = root
	dataset_id = id
	label_catalog = catalog
	for path in [
		"images/train",
		"images/val",
		"images/test",
		"labels/train",
		"labels/val",
		"labels/test",
		"masks/train",
		"masks/val",
		"masks/test",
	]:
		var error := DirAccess.make_dir_recursive_absolute(dataset_root.path_join(path))
		if error != OK:
			push_error("Cannot create dataset folder %s: %s" % [path, error])
			return false
	_write_data_yaml()
	frame_manifest_file = FileAccess.open(dataset_root.path_join("sensor_frame_manifest.jsonl"), FileAccess.WRITE)
	if frame_manifest_file == null:
		push_error("Cannot open sensor_frame_manifest.jsonl")
		return false
	return true


func write_frame(
	camera,
	frame_index: int,
	trace_time_seconds: float,
	rgb_image: Image,
	mask_image: Image,
	labels: Array,
	object_metadata: Dictionary,
	caveat: String = ""
) -> void:
	var split := _safe_split(str(camera.get("split")))
	var frame_id := "%s_%06d" % [str(camera.get("sensor_id")), frame_index]
	frame_id = frame_id.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")
	var image_path := "images/%s/%s.png" % [split, frame_id]
	var label_path := "labels/%s/%s.txt" % [split, frame_id]
	var mask_path := "masks/%s/%s.png" % [split, frame_id]

	rgb_image.save_png(dataset_root.path_join(image_path))
	mask_image.save_png(dataset_root.path_join(mask_path))
	_write_label_file(dataset_root.path_join(label_path), labels)

	var payload := {
		"dataset_id": dataset_id,
		"frame_id": frame_id,
		"camera_id": str(camera.get("sensor_id")),
		"camera_role": str(camera.get("role")),
		"split": split,
		"trace_time_seconds": trace_time_seconds,
		"image": image_path,
		"labels": label_path,
		"object_id_mask": mask_path,
		"label_count": labels.size(),
		"object_metadata": object_metadata,
		"caveat": caveat,
	}
	frame_manifest_file.store_string(JSON.stringify(payload) + "\n")
	render_manifest_frames.append(payload)


func finish(source_trace: String, source_scene: String, mask_mode: String) -> void:
	if frame_manifest_file != null:
		frame_manifest_file.close()
	var payload := {
		"render_id": "GODOT-SENSOR-SMOKE-001",
		"dataset_id": dataset_id,
		"source_trace": source_trace,
		"source_scene": source_scene,
		"renderer": "godot_3d_replay_camera",
		"label_format": "yolo_detection",
		"mask_mode": mask_mode,
		"camera_ids": _camera_ids(),
		"frame_count": render_manifest_frames.size(),
		"frames": render_manifest_frames,
		"status": "sensor_smoke_frames_generated",
		"caveat": "Synthetic labels are generated from Godot replay objects. The CV model must only consume rendered RGB frames at inference time.",
	}
	var file := FileAccess.open(dataset_root.path_join("render_manifest.json"), FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(payload, "\t") + "\n")
		file.close()


func _write_data_yaml() -> void:
	var file := FileAccess.open(dataset_root.path_join("data.yaml"), FileAccess.WRITE)
	if file == null:
		return
	file.store_line("path: .")
	file.store_line("train: images/train")
	file.store_line("val: images/val")
	file.store_line("names:")
	if label_catalog != null and label_catalog.has_method("class_names"):
		var names: Array = label_catalog.class_names()
		for index in range(names.size()):
			file.store_line("  %d: %s" % [index, names[index]])
	file.close()


func _write_label_file(path: String, labels: Array) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return
	for label in labels:
		file.store_line("%d %.6f %.6f %.6f %.6f" % [
			int(label["class_id"]),
			float(label["x_center"]),
			float(label["y_center"]),
			float(label["width"]),
			float(label["height"]),
		])
	file.close()


func _safe_split(value: String) -> String:
	var normalized := value.strip_edges().to_lower()
	if normalized in ["train", "val", "test"]:
		return normalized
	return "train"


func _camera_ids() -> Array[String]:
	var seen := {}
	var ids: Array[String] = []
	for frame in render_manifest_frames:
		var camera_id := str(frame.get("camera_id"))
		if not seen.has(camera_id):
			seen[camera_id] = true
			ids.append(camera_id)
	return ids
