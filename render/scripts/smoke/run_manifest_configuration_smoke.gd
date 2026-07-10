extends SceneTree

const MainScene := preload("res://scenes/main/Main.tscn")
const SchemaVersions := preload("res://scripts/contracts/schema_versions.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var net_path := _option(args, "--net")
	var overlay_path := _option(args, "--overlay")
	var traffic_light_trace_path := _option(args, "--traffic-light-trace")
	if net_path.is_empty() or overlay_path.is_empty():
		_fail("--net and --overlay are required")
		return
	var main := MainScene.instantiate()
	var world = main.get_node_or_null("DistrictReplayWorld")
	var overlay = main.get_node_or_null("SemanticOverlayRenderer")
	var traffic_visuals = main.get_node_or_null("TrafficLightVisualLayer")
	var bridge = main.get_node_or_null("SumoRenderBridge")
	if world == null or overlay == null or bridge == null:
		_fail("Main scene components are missing")
		return
	world.net_path = ""
	overlay.auto_render = false
	overlay.use_camera_zone_lod = false
	root.add_child(main)
	await process_frame
	var manifest_path := "user://manifest_configuration_smoke.json"
	var manifest := {
		"schema_version": SchemaVersions.RENDER_RUN_MANIFEST_SCHEMA_VERSION,
		"sumo_net": net_path,
		"semantic_overlay": overlay_path,
	}
	if not traffic_light_trace_path.is_empty():
		manifest["traffic_light_trace"] = traffic_light_trace_path
	var file := FileAccess.open(manifest_path, FileAccess.WRITE)
	if file == null:
		_fail("could not write temporary manifest")
		return
	file.store_string(JSON.stringify(manifest))
	file.close()
	if not bridge.configure_from_manifest(manifest_path):
		_fail("bridge rejected a valid temporary manifest: %s" % bridge.warnings)
		return
	await process_frame
	if int(world.lane_count) <= 0:
		_fail("manifest did not build SUMO geometry")
		return
	if int(overlay.spawned_zone_count) <= 0:
		_fail("manifest did not render semantic zones")
		return
	if traffic_visuals != null and int(traffic_visuals.spawned_light_count) <= 0:
		_fail("manifest did not render traffic-light visuals")
		return
	print("[MANIFEST_SMOKE] SUCCESS lanes=%d zones=%d traffic_lights=%d" % [
		world.lane_count,
		overlay.spawned_zone_count,
		int(traffic_visuals.spawned_light_count) if traffic_visuals != null else 0,
	])
	quit(0)


func _option(args: PackedStringArray, name: String) -> String:
	for index in range(args.size() - 1):
		if args[index] == name:
			return args[index + 1]
	return ""


func _fail(message: String) -> void:
	printerr("[MANIFEST_SMOKE] FAIL: %s" % message)
	quit(1)
