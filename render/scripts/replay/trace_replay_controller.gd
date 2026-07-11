class_name TraceReplayController
extends Node3D

const TraceReplayDataScript := preload("res://scripts/replay/trace_replay_data.gd")
const CoordinateMapperScript := preload("res://scripts/replay/coordinate_mapper.gd")
const VehicleFactoryScript := preload("res://scripts/assets/vehicle_factory.gd")
const VehiclePoolScript := preload("res://scripts/assets/vehicle_pool.gd")
const TracePlaybackClockScript := preload("res://scripts/replay/trace_playback_clock.gd")
const TraceInterpolatorScript := preload("res://scripts/replay/trace_interpolator.gd")

@export var trace_path := ""
@export var output_root := ""
@export var max_frames := 120
@export var auto_play := true
@export var frame_interval_seconds := 0.05
@export var playback_speed := 1.0
@export var loop_trace := true
@export var world_scale := 0.02
@export var asset_manifest_path := "res://resources/catalogs/VehicleAssetCatalog.tres"
@export var geometry_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var off_lane_threshold_m := 8.0

var replay_data = null
var mapper = null
var vehicle_factory = null
var vehicle_pool = null
var playback_clock = null
var interpolator = null
var active_vehicles: Dictionary = {}
var current_frame_index := 0
var largest_active_vehicle_count := 0
var frames_applied := 0
var parse_error_count := 0
var is_playing := false
var off_lane_vehicle_count := 0
var max_off_lane_distance_m := 0.0


func _ready() -> void:
	if not trace_path.is_empty():
		load_trace(trace_path, max_frames)
	if auto_play:
		play()


func _process(delta: float) -> void:
	if not is_playing or playback_clock == null or interpolator == null or not interpolator.has_frames():
		return
	var current_time := float(playback_clock.advance(delta))
	_apply_frame(interpolator.frame_at_time(current_time))
	current_frame_index = _next_frame_index_after_time(current_time)
	_apply_traffic_lights_time(current_time)


func load_trace(path: String, frame_limit: int = 0) -> bool:
	clear_trace()
	replay_data = TraceReplayDataScript.new()
	var ok: bool = replay_data.load_jsonl(path, frame_limit)
	parse_error_count = replay_data.errors.size()
	if not ok:
		for error in replay_data.errors:
			push_error(error)
		return false
	vehicle_factory = VehicleFactoryScript.new()
	if not vehicle_factory.configure(asset_manifest_path):
		for error in vehicle_factory.errors():
			push_warning(error)
	vehicle_pool = VehiclePoolScript.new()
	vehicle_pool.configure(vehicle_factory, self)
	interpolator = TraceInterpolatorScript.new()
	interpolator.configure(replay_data.frames)
	playback_clock = TracePlaybackClockScript.new()
	playback_clock.configure(
		interpolator.start_time_seconds(),
		interpolator.end_time_seconds(),
		playback_speed,
		loop_trace
	)
	mapper = CoordinateMapperScript.new()
	var geometry_node := _geometry_node()
	if geometry_node != null and geometry_node.has_method("has_geometry_bounds") and geometry_node.has_geometry_bounds():
		if geometry_node.get("world_scale") != null:
			world_scale = max(0.0001, float(geometry_node.get("world_scale")))
		mapper.configure(
			geometry_node.get_geometry_bounds_min(),
			geometry_node.get_geometry_bounds_max(),
			world_scale
		)
	else:
		mapper.configure(replay_data.bounds_min, replay_data.bounds_max, world_scale)
	current_frame_index = 0
	frames_applied = 0
	off_lane_vehicle_count = 0
	max_off_lane_distance_m = 0.0
	_apply_frame(interpolator.frame_at_time(playback_clock.current_time_seconds))
	_apply_traffic_lights_time(playback_clock.current_time_seconds)
	return true


func play() -> void:
	is_playing = replay_data != null and not replay_data.frames.is_empty()
	if playback_clock != null and is_playing:
		playback_clock.play()


func pause() -> void:
	is_playing = false
	if playback_clock != null:
		playback_clock.pause()


func clear_trace() -> void:
	pause()
	if vehicle_pool != null:
		for vehicle_id in active_vehicles.keys():
			var vehicle := active_vehicles[vehicle_id] as Node
			if vehicle != null:
				vehicle_pool.release(vehicle)
	active_vehicles.clear()
	replay_data = null
	interpolator = null
	playback_clock = null
	mapper = null
	vehicle_pool = null
	vehicle_factory = null
	current_frame_index = 0
	frames_applied = 0
	largest_active_vehicle_count = 0
	off_lane_vehicle_count = 0
	max_off_lane_distance_m = 0.0


func restart() -> void:
	current_frame_index = 0
	frames_applied = 0
	if playback_clock != null:
		playback_clock.restart()
	if interpolator != null and interpolator.has_frames():
		_apply_frame(interpolator.frame_at_time(playback_clock.current_time_seconds))
		_apply_traffic_lights_time(playback_clock.current_time_seconds)


func step_once() -> bool:
	if replay_data == null or replay_data.frames.is_empty():
		return false
	var frame = interpolator.frame_at_index(current_frame_index)
	_apply_frame(frame)
	if frame != null:
		if playback_clock != null:
			playback_clock.seek(frame.time_seconds)
		_apply_traffic_lights_time(frame.time_seconds)
	current_frame_index += 1
	if current_frame_index >= replay_data.frames.size():
		current_frame_index = 0
	return true


func run_headless_smoke(path: String, output_dir: String, frame_limit: int) -> int:
	output_root = output_dir
	if not load_trace(path, frame_limit):
		_write_summary(false)
		return 2
	frames_applied = 0
	largest_active_vehicle_count = active_vehicles.size()

	var visual_layer = get_node_or_null("../TrafficLightVisualLayer")
	if visual_layer != null and visual_layer.has_method("render_traffic_lights"):
		visual_layer.render_traffic_lights()

	var limit: int = replay_data.frames.size()
	for index in range(limit):
		var time_seconds := _headless_sample_time(index, limit)
		_apply_frame(interpolator.frame_at_time(time_seconds))
		_apply_traffic_lights_time(time_seconds)
	_write_summary(true)
	return 0


func _apply_frame(frame) -> void:
	if frame == null:
		return
	var seen := {}
	var geometry_node := _geometry_node()
	for vehicle in frame.vehicles:
		var vehicle_id := String(vehicle.vehicle_id)
		if vehicle_id.is_empty():
			continue
		if geometry_node != null and geometry_node.has_method("distance_to_nearest_lane_m"):
			var distance := float(geometry_node.distance_to_nearest_lane_m(
				float(vehicle.x),
				float(vehicle.y)
			))
			max_off_lane_distance_m = max(max_off_lane_distance_m, distance)
			if distance > off_lane_threshold_m:
				off_lane_vehicle_count += 1
		seen[vehicle_id] = true
		var node = active_vehicles.get(vehicle_id)
		if node == null:
			node = vehicle_pool.acquire(String(vehicle.vehicle_type), vehicle_id)
			if node == null:
				continue
			if node.get_parent() != self:
				add_child(node)
			active_vehicles[vehicle_id] = node
		node.apply_trace_vehicle(vehicle, mapper, geometry_node)

	for vehicle_id in active_vehicles.keys():
		if not seen.has(vehicle_id):
			var stale_node := active_vehicles[vehicle_id] as Node
			if stale_node != null:
				vehicle_pool.release(stale_node)
			active_vehicles.erase(vehicle_id)

	largest_active_vehicle_count = max(largest_active_vehicle_count, active_vehicles.size())
	frames_applied += 1


func _apply_traffic_lights_time(time_seconds: float) -> void:
	var state_layer = get_node_or_null("../TrafficLightStateLayer")
	if state_layer != null and state_layer.has_method("apply_time"):
		state_layer.apply_time(time_seconds)


func _next_frame_index_after_time(time_seconds: float) -> int:
	if replay_data == null or replay_data.frames.is_empty():
		return 0
	for index in range(replay_data.frames.size()):
		if float(replay_data.frames[index].time_seconds) > time_seconds:
			return index
	return 0 if loop_trace else replay_data.frames.size() - 1


func _write_summary(success: bool) -> void:
	if output_root.is_empty():
		return
	var error := DirAccess.make_dir_recursive_absolute(output_root)
	if error != OK:
		push_error("Cannot create output root %s: %s" % [output_root, error])
		return

	var visual_fit := _vehicle_visual_fit_summary()
	var payload := {
		"success": success,
		"loaded_frames": replay_data.loaded_frame_count() if replay_data != null else 0,
		"frames_applied": frames_applied,
		"spawned_vehicle_count": replay_data.unique_vehicle_count() if replay_data != null else 0,
		"largest_active_vehicle_count": largest_active_vehicle_count,
		"parse_error_count": parse_error_count,
		"off_lane_vehicle_count": off_lane_vehicle_count,
		"max_off_lane_distance_m": max_off_lane_distance_m,
		"world_scale": world_scale,
		"bounds_min": [mapper.bounds_min.x, mapper.bounds_min.y] if mapper != null else [],
		"bounds_max": [mapper.bounds_max.x, mapper.bounds_max.y] if mapper != null else [],
		"lane_count": _geometry_metric("lane_count"),
		"road_count": _geometry_metric("road_count"),
		"intersection_count": _geometry_metric("intersection_count"),
		"rendered_lane_count": _geometry_metric("rendered_lane_count"),
		"rendered_junction_count": _geometry_metric("rendered_junction_count"),
		"rendered_lane_mesh_count": _geometry_metric("rendered_lane_mesh_count"),
		"rendered_lane_segment_count": _geometry_metric("rendered_lane_segment_count"),
		"rendered_roadside_prop_count": _geometry_metric("rendered_roadside_prop_count"),
		"rendered_road_role_counts": _geometry_variant_metric("rendered_road_role_counts"),
		"lane_render_model": _geometry_string_metric("lane_render_model"),
		"min_lane_width_m": _geometry_float_metric("min_lane_width_m"),
		"max_lane_width_m": _geometry_float_metric("max_lane_width_m"),
		"average_lane_width_m": _geometry_float_metric("average_lane_width_m"),
		"vehicle_asset_manifest_path": asset_manifest_path,
		"vehicle_asset_catalog_path": asset_manifest_path,
		"vehicle_asset_registry_loaded": (
			vehicle_factory.manifest_loaded() if vehicle_factory != null else false
		),
		"vehicle_scene_count": (
			vehicle_factory.registered_vehicle_type_count() if vehicle_factory != null else 0
		),
		"vehicle_fallback_spawn_count": (
			vehicle_factory.fallback_spawn_count if vehicle_factory != null else 0
		),
		"vehicle_visual_fit_asset_count": int(visual_fit.get("asset_count", 0)),
		"vehicle_visual_fit_max_error_world_units": float(visual_fit.get("max_error", 0.0)),
		"vehicle_pool_model": "VehiclePool",
		"vehicle_pool_created_count": (
			vehicle_pool.created_count if vehicle_pool != null else 0
		),
		"vehicle_pool_reused_count": (
			vehicle_pool.reused_count if vehicle_pool != null else 0
		),
		"vehicle_pool_released_count": (
			vehicle_pool.released_count if vehicle_pool != null else 0
		),
		"vehicle_pool_available_count": (
			vehicle_pool.available_count() if vehicle_pool != null else 0
		),
		"trace_data_model": "TraceFrameData/TraceVehicleState",
		"trace_schema_version": replay_data.schema_version if replay_data != null else "",
		"sumo_geometry_data_model": _geometry_data_model(),
		"zone_overlay": _zone_overlay_summary(),
		"traffic_light_visuals": _traffic_light_visual_summary(),
		"playback_data_model": "TracePlaybackClock/TraceInterpolator",
		"playback_speed": playback_speed,
		"loop_trace": loop_trace,
		"trace_duration_seconds": (
			playback_clock.duration_seconds() if playback_clock != null else 0.0
		),
		"interpolated_frame_count": (
			interpolator.interpolation_count if interpolator != null else 0
		),
		"caveat": "3D-lite placeholder replay from SUMO vehicle-level trace; not final art assets.",
	}
	var summary_path := output_root.path_join("replay_summary.json")
	var file := FileAccess.open(summary_path, FileAccess.WRITE)
	if file == null:
		push_error("Cannot write replay summary: %s" % summary_path)
		return
	file.store_string(JSON.stringify(payload, "\t") + "\n")
	file.close()


func _vehicle_visual_fit_summary() -> Dictionary:
	var asset_count := 0
	var max_error := 0.0
	for raw_vehicle in active_vehicles.values():
		if raw_vehicle == null or not raw_vehicle.has_method("visual_physical_fit_error_world_units"):
			continue
		var error := float(raw_vehicle.visual_physical_fit_error_world_units())
		if error < 0.0:
			continue
		asset_count += 1
		max_error = max(max_error, error)
	return {"asset_count": asset_count, "max_error": max_error}


func _geometry_node() -> Node:
	return get_node_or_null(geometry_world_path)


func _geometry_metric(field_name: String) -> int:
	var geometry_node := _geometry_node()
	if geometry_node == null:
		return 0
	return int(geometry_node.get(field_name))


func _geometry_float_metric(field_name: String) -> float:
	var geometry_node := _geometry_node()
	if geometry_node == null:
		return 0.0
	return float(geometry_node.get(field_name))


func _geometry_variant_metric(field_name: String):
	var geometry_node := _geometry_node()
	if geometry_node == null:
		return {}
	return geometry_node.get(field_name)


func _geometry_string_metric(method_name: String) -> String:
	var geometry_node := _geometry_node()
	if geometry_node == null or not geometry_node.has_method(method_name):
		return ""
	return String(geometry_node.call(method_name))


func _geometry_data_model() -> String:
	var geometry_node := _geometry_node()
	if geometry_node == null or not geometry_node.has_method("geometry_data_model"):
		return "none"
	return String(geometry_node.geometry_data_model())


func _zone_overlay_summary() -> Dictionary:
	var overlay_renderer = get_node_or_null("../SemanticOverlayRenderer")
	if overlay_renderer != null and overlay_renderer.has_method("summary"):
		return overlay_renderer.summary()
	return {}


func _traffic_light_visual_summary() -> Dictionary:
	var visual_layer = get_node_or_null("../TrafficLightVisualLayer")
	if visual_layer != null and visual_layer.has_method("summary"):
		return visual_layer.summary()
	return {}


func _headless_sample_time(index: int, sample_count: int) -> float:
	if interpolator == null or not interpolator.has_frames():
		return 0.0
	var start_time := float(interpolator.start_time_seconds())
	var end_time := float(interpolator.end_time_seconds())
	if sample_count <= 1:
		return start_time
	var duration: float = max(0.0, end_time - start_time)
	var alpha: float = float(index) / float(sample_count)
	return start_time + duration * alpha
