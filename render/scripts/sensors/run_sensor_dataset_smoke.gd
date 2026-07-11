extends SceneTree

const CameraRigCatalogScript := preload("res://scripts/sensors/camera_rig_catalog.gd")
const CameraCalibrationLoaderScript := preload("res://scripts/sensors/camera_calibration_loader.gd")
const DetectionCameraScene := preload("res://scenes/sensors/DetectionCamera3D.tscn")
const LabelMappingCatalogScript := preload("res://scripts/sensors/label_mapping_catalog.gd")
const SensorRenderPipelineScript := preload("res://scripts/sensors/sensor_render_pipeline.gd")
const SensorDatasetWriterScript := preload("res://scripts/sensors/sensor_dataset_writer.gd")

func _init() -> void:
	print("[sensor-smoke] init")
	call_deferred("_run")


func _run() -> void:
	print("[sensor-smoke] run")
	var options := _parse_user_args()
	var trace_path := str(options.get("trace", ""))
	var net_path := str(options.get("net", ""))
	var overlay_path := str(options.get("overlay", ""))
	var dataset_root := str(options.get("dataset_root", ""))
	var dataset_id := str(options.get("dataset_id", "SYNTH-CV-GODOT-SENSOR-SMOKE"))
	var max_frames := int(options.get("max_frames", "6"))
	var scene_path := str(options.get("scene", "res://scenes/main/Main.tscn"))
	var camera_catalog_path := str(options.get("camera_catalog", "res://resources/catalogs/CameraRigCatalog.tres"))
	var camera_calibration_path := str(options.get("camera_calibration", ""))
	var label_mapping_path := str(options.get("label_mapping", "res://resources/catalogs/LabelMappingCatalog.tres"))

	if trace_path.is_empty() or dataset_root.is_empty():
		push_error("--trace and --dataset-root are required")
		quit(2)
		return

	var camera_catalog = load(camera_catalog_path) if camera_calibration_path.is_empty() else null
	var label_catalog = load(label_mapping_path)
	print("[sensor-smoke] catalogs loaded")
	if camera_calibration_path.is_empty() and not (camera_catalog is CameraRigCatalogScript):
		push_error("Camera catalog is missing or invalid: %s" % camera_catalog_path)
		quit(3)
		return
	if not (label_catalog is LabelMappingCatalogScript):
		push_error("Label mapping catalog is missing or invalid: %s" % label_mapping_path)
		quit(4)
		return

	var scene: PackedScene = load(scene_path)
	print("[sensor-smoke] scene loaded")
	if scene == null:
		push_error("Cannot load scene: %s" % scene_path)
		quit(5)
		return

	var root_node := scene.instantiate()
	var world = root_node.get_node_or_null("DistrictReplayWorld")
	if world != null:
		if not net_path.is_empty():
			world.set("net_path", net_path)
	var overlay = root_node.get_node_or_null("SemanticOverlayRenderer")
	if overlay != null:
		if not overlay_path.is_empty():
			overlay.set("overlay_path", overlay_path)
			overlay.set("auto_render", true)
	var replay = root_node.get_node_or_null("TraceReplayController")
	if replay == null:
		push_error("TraceReplayController not found in scene: %s" % scene_path)
		quit(6)
		return
	replay.set("trace_path", "")
	replay.set("auto_play", false)
	replay.set("max_frames", max_frames)

	root.add_child(root_node)
	print("[sensor-smoke] scene added")
	if not replay.load_trace(trace_path, max_frames):
		push_error("Cannot load trace for sensor smoke: %s" % trace_path)
		quit(7)
		return

	var cameras := _instantiate_cameras(
		camera_catalog,
		camera_calibration_path,
		root_node,
		world
	)
	print("[sensor-smoke] cameras=%d" % cameras.size())
	if cameras.is_empty():
		push_error("No enabled cameras in catalog: %s" % camera_catalog_path)
		quit(8)
		return

	var writer = SensorDatasetWriterScript.new()
	if not writer.configure(dataset_root, dataset_id, label_catalog):
		quit(9)
		return
	var pipeline = SensorRenderPipelineScript.new()
	print("[sensor-smoke] writer ready")

	var exported_frames := 0
	var frame_limit: int = max(1, max_frames)
	for frame_index in range(frame_limit):
		replay.step_once()
		await process_frame
		var trace_time := _trace_time(replay)
		for camera in cameras:
			camera.current = true
			root.size = camera.output_size
			var rgb := _smoke_rgb_image(camera.output_size, camera.role)
			var result: Dictionary = pipeline.capture_labels_and_mask(
				camera,
				_active_vehicle_nodes(replay),
				label_catalog,
				rgb
			)
			writer.write_frame(
				camera,
				frame_index,
				trace_time,
				rgb,
				result["mask"] as Image,
				result["labels"] as Array,
				result["object_metadata"] as Dictionary,
				"Object-ID mask smoke is generated from projected Godot replay vehicle nodes; replace mask pass with material/object-id render pass for production datasets."
			)
			exported_frames += 1

	writer.finish(trace_path, scene_path, pipeline.mask_mode)
	print("[OK] Sensor dataset smoke exported %d frames to %s" % [exported_frames, dataset_root])
	quit(0)


func _instantiate_cameras(
	camera_catalog,
	calibration_path: String,
	parent: Node,
	geometry_world: Node
) -> Array:
	var cameras: Array = []
	if not calibration_path.is_empty():
		var errors: Array[String] = []
		var loader = CameraCalibrationLoaderScript.new()
		for entry in loader.load_entries(calibration_path, errors):
			var calibrated_camera = DetectionCameraScene.instantiate()
			calibrated_camera.configure_from_calibration(entry as Dictionary, geometry_world)
			parent.add_child(calibrated_camera)
			cameras.append(calibrated_camera)
		for error in errors:
			push_warning(error)
		return cameras
	if not (camera_catalog is CameraRigCatalogScript):
		return cameras
	for raw_entry in camera_catalog.enabled_entries():
		var camera = DetectionCameraScene.instantiate()
		camera.configure_from_entry(raw_entry)
		parent.add_child(camera)
		cameras.append(camera)
	return cameras


func _active_vehicle_nodes(replay) -> Array:
	var nodes: Array = []
	for value in replay.active_vehicles.values():
		if value is Node3D:
			nodes.append(value)
	return nodes


func _trace_time(replay) -> float:
	if replay.playback_clock != null:
		return float(replay.playback_clock.current_time_seconds)
	return 0.0


func _parse_user_args() -> Dictionary:
	var parsed := {}
	var args := OS.get_cmdline_user_args()
	var index := 0
	while index < args.size():
		var arg := str(args[index])
		if arg.begins_with("--") and index + 1 < args.size():
			parsed[arg.trim_prefix("--").replace("-", "_")] = str(args[index + 1])
			index += 2
		else:
			index += 1
	return parsed


func _smoke_rgb_image(size: Vector2i, role: String) -> Image:
	var width: int = max(64, size.x)
	var height: int = max(64, size.y)
	var image := Image.create(width, height, false, Image.FORMAT_RGBA8)
	var background := Color(0.72, 0.80, 0.86)
	if role == "hospital":
		background = Color(0.82, 0.90, 0.94)
	elif role == "industrial":
		background = Color(0.70, 0.70, 0.68)
	image.fill(background)
	var road := Color(0.18, 0.19, 0.20)
	image.fill_rect(Rect2i(width / 2 - 42, 0, 84, height), road)
	image.fill_rect(Rect2i(0, height / 2 - 36, width, 72), road)
	return image
