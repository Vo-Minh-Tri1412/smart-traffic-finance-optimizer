extends SceneTree

const TRAIN_FRAME := "godot_smoke_train_000"
const VAL_FRAME := "godot_smoke_val_000"

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var options := _parse_user_args()
	var dataset_root := String(options.get("dataset_root", ""))
	var dataset_id := String(options.get("dataset_id", "SYNTH-CV-GODOT-SMOKE"))
	var width := int(options.get("width", "640"))
	var height := int(options.get("height", "640"))

	if dataset_root.is_empty():
		push_error("--dataset-root is required")
		quit(2)
		return

	_ensure_dir(dataset_root.path_join("images/train"))
	_ensure_dir(dataset_root.path_join("images/val"))
	_ensure_dir(dataset_root.path_join("labels/train"))
	_ensure_dir(dataset_root.path_join("labels/val"))

	var train_boxes := [
		{"class_id": 1, "rect": Rect2i(220, 350, 80, 42), "vehicle_type": "car"},
		{"class_id": 4, "rect": Rect2i(355, 276, 92, 48), "vehicle_type": "ambulance"},
		{"class_id": 0, "rect": Rect2i(140, 430, 44, 28), "vehicle_type": "motorbike"},
	]
	var val_boxes := [
		{"class_id": 2, "rect": Rect2i(260, 250, 128, 56), "vehicle_type": "bus"},
		{"class_id": 3, "rect": Rect2i(410, 390, 100, 54), "vehicle_type": "truck"},
	]

	_write_frame(dataset_root, "train", TRAIN_FRAME, width, height, train_boxes, Color(0.78, 0.88, 0.80))
	_write_frame(dataset_root, "val", VAL_FRAME, width, height, val_boxes, Color(0.74, 0.82, 0.90))
	_write_render_manifest(dataset_root, dataset_id, width, height)
	print("[OK] Godot synthetic CV smoke frames exported to %s" % dataset_root)
	quit(0)


func _parse_user_args() -> Dictionary:
	var parsed := {}
	var args := OS.get_cmdline_user_args()
	var index := 0
	while index < args.size():
		var arg := String(args[index])
		if arg == "--dataset-root" and index + 1 < args.size():
			parsed["dataset_root"] = String(args[index + 1])
			index += 2
		elif arg == "--dataset-id" and index + 1 < args.size():
			parsed["dataset_id"] = String(args[index + 1])
			index += 2
		elif arg == "--width" and index + 1 < args.size():
			parsed["width"] = String(args[index + 1])
			index += 2
		elif arg == "--height" and index + 1 < args.size():
			parsed["height"] = String(args[index + 1])
			index += 2
		else:
			index += 1
	return parsed


func _ensure_dir(path: String) -> void:
	var error := DirAccess.make_dir_recursive_absolute(path)
	if error != OK:
		push_error("Failed to create directory %s: %s" % [path, error])
		quit(3)


func _write_frame(
	dataset_root: String,
	split: String,
	frame_id: String,
	width: int,
	height: int,
	boxes: Array,
	background: Color
) -> void:
	var image := Image.create(width, height, false, Image.FORMAT_RGBA8)
	image.fill(background)
	_draw_district_background(image, width, height)

	for box in boxes:
		var rect := box["rect"] as Rect2i
		var class_id := int(box["class_id"])
		var color := _class_color(class_id)
		image.fill_rect(rect, color)
		_draw_box_border(image, rect, Color(0.05, 0.05, 0.05))

	var image_path := dataset_root.path_join("images/%s/%s.png" % [split, frame_id])
	var label_path := dataset_root.path_join("labels/%s/%s.txt" % [split, frame_id])
	var image_error := image.save_png(image_path)
	if image_error != OK:
		push_error("Failed to save image %s: %s" % [image_path, image_error])
		quit(4)
		return

	var label_lines := PackedStringArray()
	for box in boxes:
		label_lines.append(_to_yolo_line(int(box["class_id"]), box["rect"] as Rect2i, width, height))
	var label_file := FileAccess.open(label_path, FileAccess.WRITE)
	if label_file == null:
		push_error("Failed to open label file %s" % label_path)
		quit(5)
		return
	label_file.store_string("\n".join(label_lines) + "\n")
	label_file.close()


func _draw_district_background(image: Image, width: int, height: int) -> void:
	var road := Color(0.22, 0.23, 0.24)
	var lane := Color(0.90, 0.86, 0.55)
	var hospital := Color(0.85, 0.94, 0.98)
	var industrial := Color(0.62, 0.62, 0.64)
	var park := Color(0.38, 0.66, 0.42)

	image.fill_rect(Rect2i(width / 2 - 58, 0, 116, height), road)
	image.fill_rect(Rect2i(0, height / 2 - 50, width, 100), road)
	image.fill_rect(Rect2i(width / 2 - 4, 0, 8, height), lane)
	image.fill_rect(Rect2i(0, height / 2 - 4, width, 8), lane)

	image.fill_rect(Rect2i(32, 48, 155, 105), hospital)
	image.fill_rect(Rect2i(width - 205, 54, 170, 118), industrial)
	image.fill_rect(Rect2i(42, height - 160, 160, 108), park)


func _draw_box_border(image: Image, rect: Rect2i, color: Color) -> void:
	image.fill_rect(Rect2i(rect.position.x, rect.position.y, rect.size.x, 3), color)
	image.fill_rect(Rect2i(rect.position.x, rect.position.y + rect.size.y - 3, rect.size.x, 3), color)
	image.fill_rect(Rect2i(rect.position.x, rect.position.y, 3, rect.size.y), color)
	image.fill_rect(Rect2i(rect.position.x + rect.size.x - 3, rect.position.y, 3, rect.size.y), color)


func _class_color(class_id: int) -> Color:
	match class_id:
		0:
			return Color(0.95, 0.66, 0.28)
		1:
			return Color(0.12, 0.38, 0.90)
		2:
			return Color(0.92, 0.78, 0.15)
		3:
			return Color(0.45, 0.29, 0.18)
		4:
			return Color(0.90, 0.10, 0.12)
		_:
			return Color(0.70, 0.70, 0.70)


func _to_yolo_line(class_id: int, rect: Rect2i, width: int, height: int) -> String:
	var x_center := (float(rect.position.x) + float(rect.size.x) / 2.0) / float(width)
	var y_center := (float(rect.position.y) + float(rect.size.y) / 2.0) / float(height)
	var box_width := float(rect.size.x) / float(width)
	var box_height := float(rect.size.y) / float(height)
	return "%d %.6f %.6f %.6f %.6f" % [class_id, x_center, y_center, box_width, box_height]


func _write_render_manifest(dataset_root: String, dataset_id: String, width: int, height: int) -> void:
	var payload := {
		"render_id": "GODOT-SMOKE-001",
		"dataset_id": dataset_id,
		"source_run_id": "manual-smoke-static-scene",
		"source_engine": "godot_smoke_static_scene",
		"renderer": "godot_2d_image_smoke",
		"label_format": "yolo_detection",
		"image_size": [width, height],
		"weather_profiles": ["clear_day"],
		"lighting_profiles": ["day"],
		"camera_ids": ["CAM_SMOKE_DISTRICT_TOPDOWN"],
		"frames": [
			{"split": "train", "image": "images/train/%s.png" % TRAIN_FRAME, "labels": "labels/train/%s.txt" % TRAIN_FRAME},
			{"split": "val", "image": "images/val/%s.png" % VAL_FRAME, "labels": "labels/val/%s.txt" % VAL_FRAME},
		],
		"status": "smoke_frames_generated",
		"caveat": "This smoke export uses a simple Godot-generated image scene, not final 3D district rendering.",
	}
	var manifest_file := FileAccess.open(dataset_root.path_join("render_manifest.json"), FileAccess.WRITE)
	if manifest_file == null:
		push_error("Failed to open render_manifest.json")
		quit(6)
		return
	manifest_file.store_string(JSON.stringify(payload, "\t") + "\n")
	manifest_file.close()
