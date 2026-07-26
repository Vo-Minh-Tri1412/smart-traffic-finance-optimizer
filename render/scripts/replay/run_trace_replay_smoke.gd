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
	var output_root := String(options.get("output_root", ""))
	var max_frames := int(options.get("max_frames", "60"))

	if trace_path.is_empty():
		push_error("--trace is required")
		quit(2)
		return
	if output_root.is_empty():
		push_error("--output-root is required")
		quit(2)
		return

	var main := MainScene.instantiate()
	var world = main.get_node_or_null("DistrictReplayWorld")
	if world != null:
		world.net_path = ""
		world.spec_path = ""
	var overlay_renderer = main.get_node_or_null("SemanticOverlayRenderer")
	if overlay_renderer != null:
		overlay_renderer.auto_render = false
		overlay_renderer.overlay_path = ""
	var heatmap_renderer = main.get_node_or_null("SemanticHeatmapRenderer")
	if heatmap_renderer != null:
		heatmap_renderer.auto_render = false
		heatmap_renderer.overlay_path = ""
	var traffic_light_visual_layer = main.get_node_or_null("TrafficLightVisualLayer")
	if traffic_light_visual_layer != null:
		traffic_light_visual_layer.auto_render = false
	var preview_layer_toggles = main.get_node_or_null("PreviewLayerToggles")
	if preview_layer_toggles != null:
		preview_layer_toggles.auto_rebuild_visible_layers = false
	var controller = main.get_node_or_null("TraceReplayController")
	if controller != null:
		controller.trace_path = ""

	root.add_child(main)

	if world != null and not net_path.is_empty():
		world.build_from_sumo_net(net_path)
	elif world != null and not spec_path.is_empty():
		world.build_from_spec(spec_path)

	if overlay_renderer != null and not overlay_path.is_empty():
		overlay_renderer.render_overlay(overlay_path)

	if traffic_light_visual_layer != null and traffic_light_visual_layer.has_method("render_traffic_lights"):
		traffic_light_visual_layer.render_traffic_lights()

	if controller == null:
		push_error("TraceReplayController node not found in Main scene.")
		quit(3)
		return

	var exit_code: int = controller.run_headless_smoke(trace_path, output_root, max_frames)
	if exit_code == 0:
		print("[OK] Godot SUMO trace replay smoke wrote summary to %s" % output_root)
	quit(exit_code)


func _parse_user_args() -> Dictionary:
	var parsed := {}
	var args := OS.get_cmdline_user_args()
	var index := 0
	while index < args.size():
		var arg := String(args[index])
		if arg == "--trace" and index + 1 < args.size():
			parsed["trace"] = String(args[index + 1])
			index += 2
		elif arg == "--net" and index + 1 < args.size():
			parsed["net"] = String(args[index + 1])
			index += 2
		elif arg == "--overlay" and index + 1 < args.size():
			parsed["overlay"] = String(args[index + 1])
			index += 2
		elif arg == "--spec" and index + 1 < args.size():
			parsed["spec"] = String(args[index + 1])
			index += 2
		elif arg == "--output-root" and index + 1 < args.size():
			parsed["output_root"] = String(args[index + 1])
			index += 2
		elif arg == "--max-frames" and index + 1 < args.size():
			parsed["max_frames"] = String(args[index + 1])
			index += 2
		else:
			index += 1
	return parsed
