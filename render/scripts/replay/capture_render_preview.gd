extends SceneTree

const MainScene := preload("res://scenes/main/Main.tscn")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var options := _parse_user_args()
	var trace_path := String(options.get("trace", ""))
	var spec_path := String(options.get("spec", ""))
	var net_path := String(options.get("net", ""))
	var overlay_path := String(options.get("overlay", ""))
	var output_path := String(options.get("out", ""))
	var max_frames := int(options.get("max_frames", "30"))
	var width := int(options.get("width", "1280"))
	var height := int(options.get("height", "720"))
	var camera_mode := String(options.get("camera", "angled"))
	var camera_size := float(options.get("camera_size", "0"))
	var show_roads := _truthy(String(options.get("show_roads", "true")))
	var show_zones := _truthy(String(options.get("show_zones", "true")))
	var show_vehicles := _truthy(String(options.get("show_vehicles", "true")))
	var show_traffic_lights := _truthy(String(options.get("show_traffic_lights", "true")))

	if output_path.is_empty():
		push_error("--out is required")
		quit(2)
		return

	root.size = Vector2i(max(320, width), max(240, height))

	var main := MainScene.instantiate()
	var world = main.get_node_or_null("DistrictReplayWorld")
	if world != null:
		world.net_path = ""
		world.spec_path = ""
		world.visible = show_roads
	var overlay_renderer = main.get_node_or_null("SemanticOverlayRenderer")
	if overlay_renderer != null:
		overlay_renderer.auto_render = false
		overlay_renderer.overlay_path = ""
		overlay_renderer.visible = show_zones
	var traffic_light_visual_layer = main.get_node_or_null("TrafficLightVisualLayer")
	if traffic_light_visual_layer != null:
		traffic_light_visual_layer.auto_render = false
		traffic_light_visual_layer.visible = show_traffic_lights
	var traffic_light_state_layer = main.get_node_or_null("TrafficLightStateLayer")
	if traffic_light_state_layer != null:
		traffic_light_state_layer.visible = show_traffic_lights
	var controller = main.get_node_or_null("TraceReplayController")
	if controller != null:
		controller.trace_path = ""
		controller.auto_play = false
		controller.max_frames = max_frames
		controller.visible = show_vehicles
	var layer_toggles = main.get_node_or_null("PreviewLayerToggles")
	if layer_toggles != null:
		layer_toggles.set("show_roads", show_roads)
		layer_toggles.set("show_zones", show_zones)
		layer_toggles.set("show_vehicles", show_vehicles)
		layer_toggles.set("show_traffic_lights", show_traffic_lights)

	root.add_child(main)

	if world != null and not net_path.is_empty():
		world.build_from_sumo_net(net_path)
	elif world != null and not spec_path.is_empty():
		world.build_from_spec(spec_path)

	if overlay_renderer != null and not overlay_path.is_empty() and show_zones:
		overlay_renderer.render_overlay(overlay_path)

	if (
		traffic_light_visual_layer != null
		and traffic_light_visual_layer.has_method("render_traffic_lights")
		and show_traffic_lights
	):
		traffic_light_visual_layer.render_traffic_lights()

	if controller != null and not trace_path.is_empty() and show_vehicles:
		if not controller.load_trace(trace_path, max_frames):
			push_warning("Cannot load trace for preview capture: %s" % trace_path)
		else:
			var frame_steps: int = clamp(max_frames, 1, 45)
			for _index in range(frame_steps):
				controller.step_once()

	var camera := main.get_node_or_null("Camera3D") as Camera3D
	if camera != null:
		_configure_camera(camera, world, camera_mode, camera_size)

	for _index in range(4):
		await process_frame
	if camera != null:
		_configure_camera(camera, world, camera_mode, camera_size)
	await process_frame

	var image := root.get_texture().get_image()
	if image == null or image.is_empty():
		push_error("Viewport image capture failed.")
		quit(3)
		return
	var error := image.save_png(output_path)
	if error != OK:
		push_error("Cannot write preview screenshot %s: %s" % [output_path, error])
		quit(4)
		return

	_write_summary(output_path, main, image.get_width(), image.get_height())
	print("[OK] Render preview screenshot wrote %s" % output_path)
	quit(0)


func _configure_camera(camera: Camera3D, world, camera_mode: String, override_size: float) -> void:
	if camera.has_method("fit_to_world"):
		camera.set("use_top_down_preview", camera_mode == "topdown")
		camera.fit_to_world()
	if override_size > 0.0:
		camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		camera.size = override_size
	if camera_mode == "angled":
		camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		if world != null and world.has_method("has_geometry_bounds") and world.has_geometry_bounds():
			var bounds_min: Vector2 = world.get_geometry_bounds_min()
			var bounds_max: Vector2 = world.get_geometry_bounds_max()
			var world_scale: float = float(world.get("world_scale"))
			var width_world: float = abs(bounds_max.x - bounds_min.x) * world_scale
			var depth_world: float = abs(bounds_max.y - bounds_min.y) * world_scale
			var fitted_size: float = max(width_world, depth_world)
			if override_size <= 0.0:
				camera.size = clamp(fitted_size * 1.08, 30.0, 260.0)
			camera.position = Vector3(0.0, max(42.0, camera.size * 2.15), camera.size * 0.55)
			camera.look_at(Vector3.ZERO, Vector3.UP)
	camera.current = true


func _write_summary(output_path: String, main: Node, width: int, height: int) -> void:
	var world = main.get_node_or_null("DistrictReplayWorld")
	var overlay = main.get_node_or_null("SemanticOverlayRenderer")
	var tls_visuals = main.get_node_or_null("TrafficLightVisualLayer")
	var payload := {
		"image": output_path,
		"width": width,
		"height": height,
		"lane_count": int(world.get("lane_count")) if world != null else 0,
		"rendered_lane_count": int(world.get("rendered_lane_count")) if world != null else 0,
		"rendered_junction_count": int(world.get("rendered_junction_count")) if world != null else 0,
		"rendered_roadside_prop_count": int(world.get("rendered_roadside_prop_count")) if world != null else 0,
		"rendered_road_role_counts": world.get("rendered_road_role_counts") if world != null else {},
		"visible_layers": {
			"roads": bool(world.visible) if world != null else false,
			"zones": bool(overlay.visible) if overlay != null else false,
			"vehicles": bool(main.get_node_or_null("TraceReplayController").visible) if main.get_node_or_null("TraceReplayController") != null else false,
			"traffic_lights": bool(tls_visuals.visible) if tls_visuals != null else false,
		},
		"zone_overlay": overlay.summary() if overlay != null and overlay.has_method("summary") else {},
		"traffic_light_visuals": tls_visuals.summary() if tls_visuals != null and tls_visuals.has_method("summary") else {},
	}
	var summary_path := output_path.get_basename() + ".summary.json"
	var file := FileAccess.open(summary_path, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(payload, "\t") + "\n")
	file.close()


func _parse_user_args() -> Dictionary:
	var parsed := {}
	var args := OS.get_cmdline_user_args()
	var index := 0
	while index < args.size():
		var arg := String(args[index])
		if arg.begins_with("--") and index + 1 < args.size():
			parsed[arg.trim_prefix("--").replace("-", "_")] = String(args[index + 1])
			index += 2
		else:
			index += 1
	return parsed


func _truthy(value: String) -> bool:
	var normalized := value.strip_edges().to_lower()
	return normalized in ["1", "true", "yes", "y", "on"]
