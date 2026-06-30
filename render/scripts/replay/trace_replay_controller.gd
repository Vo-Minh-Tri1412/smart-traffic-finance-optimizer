class_name TraceReplayController
extends Node3D

const TraceReplayDataScript := preload("res://scripts/replay/trace_replay_data.gd")
const CoordinateMapperScript := preload("res://scripts/replay/coordinate_mapper.gd")
const VehicleScene := preload("res://scenes/vehicles/VehicleBase.tscn")

@export var trace_path := ""
@export var output_root := ""
@export var max_frames := 120
@export var auto_play := true
@export var frame_interval_seconds := 0.05
@export var world_scale := 0.02

var replay_data = null
var mapper = null
var active_vehicles: Dictionary = {}
var current_frame_index := 0
var elapsed_since_frame := 0.0
var largest_active_vehicle_count := 0
var frames_applied := 0
var parse_error_count := 0
var is_playing := false


func _ready() -> void:
	if not trace_path.is_empty():
		load_trace(trace_path, max_frames)
	if auto_play:
		play()


func _process(delta: float) -> void:
	if not is_playing or replay_data == null or replay_data.frames.is_empty():
		return
	elapsed_since_frame += delta
	if elapsed_since_frame < frame_interval_seconds:
		return
	elapsed_since_frame = 0.0
	step_once()


func load_trace(path: String, frame_limit: int = 0) -> bool:
	replay_data = TraceReplayDataScript.new()
	var ok: bool = replay_data.load_jsonl(path, frame_limit)
	parse_error_count = replay_data.errors.size()
	if not ok:
		for error in replay_data.errors:
			push_error(error)
		return false
	mapper = CoordinateMapperScript.new()
	mapper.configure(replay_data.bounds_min, replay_data.bounds_max, world_scale)
	current_frame_index = 0
	frames_applied = 0
	_apply_frame(replay_data.frames[0])
	return true


func play() -> void:
	is_playing = replay_data != null and not replay_data.frames.is_empty()


func pause() -> void:
	is_playing = false


func restart() -> void:
	current_frame_index = 0
	frames_applied = 0
	if replay_data != null and not replay_data.frames.is_empty():
		_apply_frame(replay_data.frames[0])


func step_once() -> bool:
	if replay_data == null or replay_data.frames.is_empty():
		return false
	_apply_frame(replay_data.frames[current_frame_index])
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
	var limit: int = replay_data.frames.size()
	for index in range(limit):
		_apply_frame(replay_data.frames[index])
	_write_summary(true)
	return 0


func _apply_frame(frame: Dictionary) -> void:
	var seen := {}
	for vehicle in frame.get("vehicles", []):
		var vehicle_dict := vehicle as Dictionary
		var vehicle_id := String(vehicle_dict.get("vehicle_id", ""))
		if vehicle_id.is_empty():
			continue
		seen[vehicle_id] = true
		var node = active_vehicles.get(vehicle_id)
		if node == null:
			node = VehicleScene.instantiate()
			node.configure(String(vehicle_dict.get("vehicle_type", "UNKNOWN")), vehicle_id)
			add_child(node)
			active_vehicles[vehicle_id] = node
		node.apply_trace_vehicle(vehicle_dict, mapper)

	for vehicle_id in active_vehicles.keys():
		if not seen.has(vehicle_id):
			var stale_node := active_vehicles[vehicle_id] as Node
			if stale_node != null:
				stale_node.queue_free()
			active_vehicles.erase(vehicle_id)

	largest_active_vehicle_count = max(largest_active_vehicle_count, active_vehicles.size())
	frames_applied += 1


func _write_summary(success: bool) -> void:
	if output_root.is_empty():
		return
	var error := DirAccess.make_dir_recursive_absolute(output_root)
	if error != OK:
		push_error("Cannot create output root %s: %s" % [output_root, error])
		return

	var payload := {
		"success": success,
		"loaded_frames": replay_data.loaded_frame_count() if replay_data != null else 0,
		"frames_applied": frames_applied,
		"spawned_vehicle_count": replay_data.unique_vehicle_count() if replay_data != null else 0,
		"largest_active_vehicle_count": largest_active_vehicle_count,
		"parse_error_count": parse_error_count,
		"world_scale": world_scale,
		"bounds_min": [mapper.bounds_min.x, mapper.bounds_min.y] if mapper != null else [],
		"bounds_max": [mapper.bounds_max.x, mapper.bounds_max.y] if mapper != null else [],
		"caveat": "3D-lite placeholder replay from SUMO vehicle-level trace; not final art assets.",
	}
	var summary_path := output_root.path_join("replay_summary.json")
	var file := FileAccess.open(summary_path, FileAccess.WRITE)
	if file == null:
		push_error("Cannot write replay summary: %s" % summary_path)
		return
	file.store_string(JSON.stringify(payload, "\t") + "\n")
	file.close()
