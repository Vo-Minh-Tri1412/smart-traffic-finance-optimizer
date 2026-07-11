class_name TraceVehicleState
extends RefCounted

var vehicle_id := ""
var vehicle_type := "UNKNOWN"
var x := 0.0
var y := 0.0
var speed := 0.0
var angle := 0.0
var lane_id := ""
var road_id := ""
var length_m := 0.0
var width_m := 0.0
var height_m := 0.0
var ground_clearance_m := 0.0
var elevation_m := 0.0
var pos_lat_m := 0.0
var lateral_speed_mps := 0.0
var acceleration_mps2 := 0.0
var elevation_source := ""
var reference_point := ""


func populate_from_dictionary(
	vehicle: Dictionary,
	line_number: int,
	errors: Array[String],
	require_geometry := false
) -> bool:
	for key in ["vehicle_id", "vehicle_type", "x", "y", "speed", "angle"]:
		if not vehicle.has(key):
			errors.append("Line %d vehicle missing required key: %s" % [line_number, key])
			return false

	vehicle_id = String(vehicle.get("vehicle_id", ""))
	vehicle_type = String(vehicle.get("vehicle_type", "UNKNOWN"))
	x = float(vehicle.get("x", 0.0))
	y = float(vehicle.get("y", 0.0))
	speed = float(vehicle.get("speed", 0.0))
	angle = float(vehicle.get("angle", 0.0))
	lane_id = String(vehicle.get("lane_id", ""))
	road_id = String(vehicle.get("road_id", ""))
	length_m = float(vehicle.get("length_m", 0.0))
	width_m = float(vehicle.get("width_m", 0.0))
	height_m = float(vehicle.get("height_m", 0.0))
	ground_clearance_m = float(vehicle.get("ground_clearance_m", 0.0))
	elevation_m = float(vehicle.get("elevation_m", 0.0))
	pos_lat_m = float(vehicle.get("pos_lat_m", 0.0))
	lateral_speed_mps = float(vehicle.get("lateral_speed_mps", 0.0))
	acceleration_mps2 = float(vehicle.get("acceleration_mps2", 0.0))
	elevation_source = String(vehicle.get("elevation_source", ""))
	reference_point = String(vehicle.get("reference_point", ""))
	if require_geometry:
		for key in [
			"length_m",
			"width_m",
			"height_m",
			"ground_clearance_m",
			"elevation_m",
			"pos_lat_m",
			"reference_point",
		]:
			if not vehicle.has(key):
				errors.append("Line %d vehicle_trace.v2 missing geometry key: %s" % [line_number, key])
				return false
		if min(length_m, min(width_m, height_m)) <= 0.0:
			errors.append("Line %d vehicle_trace.v2 has invalid physical dimensions." % line_number)
			return false
		if reference_point != "front_bumper_center":
			errors.append("Line %d vehicle_trace.v2 has unsupported reference_point." % line_number)
			return false

	if vehicle_id.is_empty():
		errors.append("Line %d vehicle_id must not be empty." % line_number)
		return false
	return true


func position_2d() -> Vector2:
	return Vector2(x, y)


func to_dictionary() -> Dictionary:
	return {
		"vehicle_id": vehicle_id,
		"vehicle_type": vehicle_type,
		"x": x,
		"y": y,
		"speed": speed,
		"angle": angle,
		"lane_id": lane_id,
		"road_id": road_id,
		"length_m": length_m,
		"width_m": width_m,
		"height_m": height_m,
		"ground_clearance_m": ground_clearance_m,
		"elevation_m": elevation_m,
		"pos_lat_m": pos_lat_m,
		"lateral_speed_mps": lateral_speed_mps,
		"acceleration_mps2": acceleration_mps2,
		"elevation_source": elevation_source,
		"reference_point": reference_point,
	}
