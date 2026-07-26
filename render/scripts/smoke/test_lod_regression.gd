extends SceneTree

const SemanticOverlayRendererScript = preload("res://scripts/zones/semantic_overlay_renderer.gd")

var errors = []

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	print("[LOD_TEST] Starting LOD regression smoke test")
	
	var overlay_path = ""
	
	# Create tree root
	var test_root = Node3D.new()
	test_root.name = "TestRoot"
	root.add_child(test_root)
	
	# Create camera for LOD target
	var camera = Node3D.new()
	camera.name = "Camera3D"
	test_root.add_child(camera)
	
	# Create renderer
	var renderer = SemanticOverlayRendererScript.new()
	renderer.name = "SemanticOverlayRenderer"
	test_root.add_child(renderer)
	
	# Configure renderer
	renderer.zone_lod_target_path = renderer.get_path_to(camera)
	# Disable real world dependency
	renderer.geometry_world_path = NodePath("")
	renderer.auto_render = false
	renderer.use_camera_zone_lod = true
	renderer.zone_lod_radius_m = 50.0
	renderer.zone_lod_rebuild_distance_m = 100.0
	renderer.zone_lod_update_interval_seconds = 0.0 # Force update on every process
	renderer.fallback_ring_radius = 200.0
	
	# Set camera to cover zone_1 (fallback position at 200, 0, 0)
	camera.global_position = Vector3(200.0, 0.0, 0.0)
	
	var args = OS.get_cmdline_user_args()
	for i in range(args.size()):
		if args[i] == "--overlay" and i + 1 < args.size():
			overlay_path = args[i+1]
			
	if overlay_path == "":
		_fail("Must provide --overlay")
		return
			
	print("[LOD_TEST] Using overlay: ", overlay_path)
	
	var success = renderer.render_overlay(overlay_path)
	if not success:
		_fail("Failed to render overlay. Errors: " + str(renderer.errors))
		return
		
	var summary_1 = renderer.summary()
	print("[LOD_TEST] Initial summary: ", summary_1)
	
	if summary_1["rebuild_count"] != 1:
		_fail("Expected 1 rebuild for initial render, got " + str(summary_1["rebuild_count"]))
		return
	if summary_1["spawned_neutral_zone_count"] != 1:
		_fail("Expected the nearby neutral zone to stream in without a global quota.")
		return
		
	var initial_zones = []
	for child in renderer.get_children():
		if child.is_in_group("generated_zone_visual"):
			initial_zones.append(child)
	if initial_zones.size() != 1:
		_fail("Expected 1 initial zone spawned, got " + str(initial_zones.size()))
		return
	var pos1 = initial_zones[0].position
	if pos1.x < 150.0:
		_fail("Expected initial zone to be zone 1 around x=200, got position " + str(pos1))
		return
		
	# Move camera slightly (less than rebuild distance)
	camera.global_position = Vector3(210.0, 0.0, 0.0)
	renderer._process(0.1)
	
	var summary_2 = renderer.summary()
	if summary_2["rebuild_count"] != 1:
		_fail("Expected no rebuilds on small move, got " + str(summary_2["rebuild_count"]))
		return
		
	# Move camera beyond rebuild distance to cover zone_2 (fallback position at -200, 0, 0)
	camera.global_position = Vector3(-200.0, 0.0, 0.0)
	renderer._process(0.1)
	
	var summary_3 = renderer.summary()
	print("[LOD_TEST] Final summary: ", summary_3)
	
	if summary_3["rebuild_count"] != 2:
		_fail("Expected rebuild count to increment to 2, got " + str(summary_3["rebuild_count"]))
		return
	if summary_3["streamed_in_zone_count"] != 2 or summary_3["streamed_out_zone_count"] != 1:
		_fail("Expected incremental zone streaming to retain the local set and swap only on travel.")
		return
		
	var final_zones = []
	for child in renderer.get_children():
		if child.is_in_group("generated_zone_visual"):
			final_zones.append(child)
	if final_zones.size() != 1:
		_fail("Expected 1 final zone spawned, got " + str(final_zones.size()))
		return
	var pos2 = final_zones[0].position
	if pos2.x > -150.0:
		_fail("Expected final zone to be zone 2 around x=-200, got position " + str(pos2))
		return
		
	print("[LOD_TEST] SUCCESS")
	quit(0)

func _fail(msg: String) -> void:
	printerr("[LOD_TEST] FAIL: " + msg)
	quit(1)
