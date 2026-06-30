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


func populate_from_dictionary(vehicle: Dictionary, line_number: int, errors: Array[String]) -> bool:
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
	}
