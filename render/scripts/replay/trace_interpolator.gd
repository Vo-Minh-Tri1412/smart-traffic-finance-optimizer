class_name TraceInterpolator
extends RefCounted

const TraceFrameDataScript := preload("res://scripts/replay/trace_frame_data.gd")
const TraceVehicleStateScript := preload("res://scripts/replay/trace_vehicle_state.gd")

var frames: Array = []
var interpolation_count := 0


func configure(trace_frames: Array) -> void:
	frames = trace_frames.duplicate()
	frames.sort_custom(Callable(self, "_sort_frame_by_time"))
	interpolation_count = 0


func has_frames() -> bool:
	return not frames.is_empty()


func start_time_seconds() -> float:
	return float(frames[0].time_seconds) if has_frames() else 0.0


func end_time_seconds() -> float:
	return float(frames[frames.size() - 1].time_seconds) if has_frames() else 0.0


func frame_at_time(time_seconds: float):
	if frames.is_empty():
		return null
	if frames.size() == 1:
		return frames[0]
	if time_seconds <= float(frames[0].time_seconds):
		return frames[0]
	if time_seconds >= float(frames[frames.size() - 1].time_seconds):
		return frames[frames.size() - 1]

	var right_index := 1
	while right_index < frames.size() and float(frames[right_index].time_seconds) < time_seconds:
		right_index += 1
	var right = frames[right_index]
	var left = frames[right_index - 1]
	var left_time: float = float(left.time_seconds)
	var right_time: float = float(right.time_seconds)
	var span: float = max(0.000001, right_time - left_time)
	var alpha: float = clamp((time_seconds - left_time) / span, 0.0, 1.0)
	interpolation_count += 1
	return _interpolate_frame(left, right, alpha, time_seconds)


func frame_at_index(index: int):
	if frames.is_empty():
		return null
	return frames[clamp(index, 0, frames.size() - 1)]


func _interpolate_frame(left, right, alpha: float, time_seconds: float):
	var output = TraceFrameDataScript.new()
	output.schema_version = String(left.schema_version)
	output.timestep = int(round(lerp(float(left.timestep), float(right.timestep), alpha)))
	output.time_seconds = time_seconds
	output.district_id = String(left.district_id)
	output.scenario_id = String(left.scenario_id)
	output.controller_id = String(left.controller_id)
	output.engine_id = String(left.engine_id)
	output.vehicles = _interpolate_vehicles(left.vehicles, right.vehicles, alpha)
	return output


func _interpolate_vehicles(left_vehicles: Array, right_vehicles: Array, alpha: float) -> Array:
	var right_by_id := {}
	for vehicle in right_vehicles:
		right_by_id[String(vehicle.vehicle_id)] = vehicle

	var seen := {}
	var output: Array = []
	for left_vehicle in left_vehicles:
		var vehicle_id := String(left_vehicle.vehicle_id)
		seen[vehicle_id] = true
		if right_by_id.has(vehicle_id):
			output.append(_interpolate_vehicle(left_vehicle, right_by_id[vehicle_id], alpha))
		else:
			output.append(_copy_vehicle(left_vehicle))

	for right_vehicle in right_vehicles:
		var vehicle_id := String(right_vehicle.vehicle_id)
		if not seen.has(vehicle_id):
			output.append(_copy_vehicle(right_vehicle))
	return output


func _interpolate_vehicle(left, right, alpha: float):
	var output = TraceVehicleStateScript.new()
	output.vehicle_id = String(left.vehicle_id)
	output.vehicle_type = String(left.vehicle_type)
	output.x = lerp(float(left.x), float(right.x), alpha)
	output.y = lerp(float(left.y), float(right.y), alpha)
	output.speed = lerp(float(left.speed), float(right.speed), alpha)
	output.angle = _lerp_angle_degrees(float(left.angle), float(right.angle), alpha)
	output.lane_id = String(left.lane_id) if alpha < 0.5 else String(right.lane_id)
	output.road_id = String(left.road_id) if alpha < 0.5 else String(right.road_id)
	output.length_m = float(left.length_m)
	output.width_m = float(left.width_m)
	output.height_m = float(left.height_m)
	output.ground_clearance_m = float(left.ground_clearance_m)
	output.elevation_m = lerp(float(left.elevation_m), float(right.elevation_m), alpha)
	output.pos_lat_m = lerp(float(left.pos_lat_m), float(right.pos_lat_m), alpha)
	output.lateral_speed_mps = lerp(
		float(left.lateral_speed_mps), float(right.lateral_speed_mps), alpha
	)
	output.acceleration_mps2 = lerp(
		float(left.acceleration_mps2), float(right.acceleration_mps2), alpha
	)
	output.elevation_source = (
		String(left.elevation_source) if alpha < 0.5 else String(right.elevation_source)
	)
	output.reference_point = String(left.reference_point)
	return output


func _copy_vehicle(source):
	var output = TraceVehicleStateScript.new()
	output.vehicle_id = String(source.vehicle_id)
	output.vehicle_type = String(source.vehicle_type)
	output.x = float(source.x)
	output.y = float(source.y)
	output.speed = float(source.speed)
	output.angle = float(source.angle)
	output.lane_id = String(source.lane_id)
	output.road_id = String(source.road_id)
	output.length_m = float(source.length_m)
	output.width_m = float(source.width_m)
	output.height_m = float(source.height_m)
	output.ground_clearance_m = float(source.ground_clearance_m)
	output.elevation_m = float(source.elevation_m)
	output.pos_lat_m = float(source.pos_lat_m)
	output.lateral_speed_mps = float(source.lateral_speed_mps)
	output.acceleration_mps2 = float(source.acceleration_mps2)
	output.elevation_source = String(source.elevation_source)
	output.reference_point = String(source.reference_point)
	return output


func _lerp_angle_degrees(left_angle: float, right_angle: float, alpha: float) -> float:
	var delta: float = fmod((right_angle - left_angle + 540.0), 360.0) - 180.0
	return fmod(left_angle + delta * alpha + 360.0, 360.0)


func _sort_frame_by_time(left, right) -> bool:
	return float(left.time_seconds) < float(right.time_seconds)
