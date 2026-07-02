extends SceneTree

const TinyZonePreviewScene := preload("res://scenes/debug/TinyZonePreview.tscn")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var options := _parse_user_args()
	var output_root := String(options.get("output_root", ""))
	if output_root.is_empty():
		push_error("--output-root is required")
		quit(2)
		return

	var preview := TinyZonePreviewScene.instantiate()
	root.add_child(preview)
	await process_frame

	var summary := {}
	if preview.has_method("summary"):
		summary = preview.summary()
	var dir := DirAccess.open("res://")
	if dir != null:
		dir.make_dir_recursive(ProjectSettings.globalize_path(output_root))
	var summary_path := ProjectSettings.globalize_path(output_root.path_join("tiny_zone_preview_summary.json"))
	var file := FileAccess.open(summary_path, FileAccess.WRITE)
	if file == null:
		push_error("Could not write summary: %s" % summary_path)
		quit(3)
		return
	file.store_string(JSON.stringify(summary, "\t") + "\n")
	file.close()

	if int(summary.get("spawned_zone_count", 0)) < 4:
		push_error("Tiny zone preview spawned fewer than 4 zones.")
		quit(4)
		return
	if int(summary.get("building_visual_count", 0)) < 4:
		push_error("Tiny zone preview spawned too few building visuals.")
		quit(5)
		return
	if int(summary.get("spawned_vehicle_count", 0)) < 1:
		push_error("Tiny zone preview spawned no vehicles.")
		quit(6)
		return
	print("[OK] Tiny zone preview smoke wrote summary to %s" % summary_path)
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
