class_name ObjectIdRegistry
extends RefCounted

var object_ids_by_vehicle_id: Dictionary = {}
var metadata_by_object_id: Dictionary = {}
var next_object_id := 1


func reset() -> void:
	object_ids_by_vehicle_id.clear()
	metadata_by_object_id.clear()
	next_object_id = 1


func register_vehicle(vehicle_id: String, vehicle_type: String, class_id: int) -> int:
	if object_ids_by_vehicle_id.has(vehicle_id):
		return int(object_ids_by_vehicle_id[vehicle_id])
	var object_id := next_object_id
	next_object_id += 1
	object_ids_by_vehicle_id[vehicle_id] = object_id
	metadata_by_object_id[object_id] = {
		"vehicle_id": vehicle_id,
		"vehicle_type": vehicle_type,
		"class_id": class_id,
		"color": color_for_object_id(object_id).to_html(false),
	}
	return object_id


func color_for_object_id(object_id: int) -> Color:
	var r := float(object_id & 0xFF) / 255.0
	var g := float((object_id >> 8) & 0xFF) / 255.0
	var b := float((object_id >> 16) & 0xFF) / 255.0
	return Color(r, g, b, 1.0)


func metadata() -> Dictionary:
	return metadata_by_object_id.duplicate(true)
