extends SceneTree

const TinyAuthoringMapScene := preload("res://scenes/authoring/TinyAuthoringMap.tscn")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var options := _parse_user_args()
	var output_root := String(options.get("output_root", ""))
	if output_root.is_empty():
		push_error("--output-root is required")
		quit(2)
		return

	var scene := TinyAuthoringMapScene.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame
	var summary: Dictionary = scene.summary() if scene.has_method("summary") else {}
	var summary_path := ProjectSettings.globalize_path(output_root.path_join("tiny_authoring_map_summary.json"))
	DirAccess.make_dir_recursive_absolute(summary_path.get_base_dir())
	var file := FileAccess.open(summary_path, FileAccess.WRITE)
	if file == null:
		push_error("Could not write tiny authoring map summary: %s" % summary_path)
		quit(3)
		return
	file.store_string(JSON.stringify(summary, "\t") + "\n")
	file.close()

	if int(summary.get("zone_lot_count", 0)) < 4:
		push_error("Tiny authoring map has fewer than 4 zone lots.")
		quit(4)
		return
	if int(summary.get("building_visual_count", 0)) < 8:
		push_error("Tiny authoring map spawned too few building visuals.")
		quit(5)
		return
	if int(summary.get("road_count", 0)) < 4:
		push_error("Tiny authoring map has too few roads.")
		quit(6)
		return
	print("[OK] Tiny authoring map smoke wrote summary to %s" % summary_path)
	quit(0)


func _parse_user_args() -> Dictionary:
	var parsed := {}
	var args := OS.get_cmdline_user_args()
	var index := 0
	while index < args.size():
		var arg := String(args[index])
		if arg == "--output-root" and index + 1 < args.size():
			parsed["output_root"] = String(args[index + 1])
			index += 2
		else:
			index += 1
	return parsed
