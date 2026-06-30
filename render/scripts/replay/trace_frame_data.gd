class_name TraceFrameData
extends RefCounted

const TraceVehicleStateScript := preload("res://scripts/replay/trace_vehicle_state.gd")
const SchemaVersionsScript := preload("res://scripts/contracts/schema_versions.gd")

var schema_version := ""
var timestep := 0
var time_seconds := 0.0
var district_id := ""
var scenario_id := ""
var controller_id := ""
var engine_id := ""
var vehicles: Array = []


func populate_from_dictionary(frame: Dictionary, line_number: int, errors: Array[String]) -> bool:
	if not SchemaVersionsScript.require_supported_version(
		frame,
		"schema_version",
		SchemaVersionsScript.supported_trace_frame_versions(),
		errors,
		"Line %d trace frame" % line_number
	):
		return false
	var required := [
		"timestep",
		"time_seconds",
		"district_id",
		"scenario_id",
		"controller_id",
		"engine_id",
		"vehicles",
	]
	for key in required:
		if not frame.has(key):
			errors.append("Line %d missing required key: %s" % [line_number, key])
			return false
	if typeof(frame["vehicles"]) != TYPE_ARRAY:
		errors.append("Line %d has non-array vehicles field." % line_number)
		return false

	schema_version = String(frame.get("schema_version", ""))
	timestep = int(frame.get("timestep", 0))
	time_seconds = float(frame.get("time_seconds", 0.0))
	district_id = String(frame.get("district_id", ""))
	scenario_id = String(frame.get("scenario_id", ""))
	controller_id = String(frame.get("controller_id", ""))
	engine_id = String(frame.get("engine_id", ""))
	vehicles.clear()

	for raw_vehicle in frame["vehicles"]:
		if typeof(raw_vehicle) != TYPE_DICTIONARY:
			errors.append("Line %d has a non-object vehicle entry." % line_number)
			return false
		var vehicle_state = TraceVehicleStateScript.new()
		if not vehicle_state.populate_from_dictionary(raw_vehicle as Dictionary, line_number, errors):
			return false
		vehicles.append(vehicle_state)
	return true


func vehicle_count() -> int:
	return vehicles.size()


func vehicle_ids() -> Array[String]:
	var ids: Array[String] = []
	for vehicle in vehicles:
		ids.append(String(vehicle.vehicle_id))
	return ids


func to_dictionary() -> Dictionary:
	var vehicle_rows: Array = []
	for vehicle in vehicles:
		vehicle_rows.append(vehicle.to_dictionary())
	return {
		"schema_version": schema_version,
		"timestep": timestep,
		"time_seconds": time_seconds,
		"district_id": district_id,
		"scenario_id": scenario_id,
		"controller_id": controller_id,
		"engine_id": engine_id,
		"vehicles": vehicle_rows,
	}
