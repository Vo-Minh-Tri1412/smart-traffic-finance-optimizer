extends SceneTree

const MainScene := preload("res://scenes/main/Main.tscn")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var options := _parse_user_args()
	var trace_path := String(options.get("trace", ""))
	var spec_path := String(options.get("spec", ""))
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
	root.add_child(main)

	var world = main.get_node_or_null("DistrictReplayWorld")
	if world != null and not spec_path.is_empty():
		world.build_from_spec(spec_path)

	var controller = main.get_node_or_null("TraceReplayController")
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
