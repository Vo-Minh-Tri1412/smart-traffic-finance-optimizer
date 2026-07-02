class_name SensorRenderPipeline
extends RefCounted

const ObjectIdRegistryScript := preload("res://scripts/sensors/object_id_registry.gd")

var object_registry = ObjectIdRegistryScript.new()
var mask_mode := "projected_object_id_mask_smoke"


func capture_labels_and_mask(camera, vehicles: Array, label_catalog, viewport_image: Image) -> Dictionary:
	object_registry.reset()
	var viewport_size := viewport_image.get_size()
	var mask := Image.create(viewport_size.x, viewport_size.y, false, Image.FORMAT_RGBA8)
	mask.fill(Color.BLACK)
	var labels: Array = []

	for node in vehicles:
		if not (node is Node3D):
			continue
		var vehicle_id := _vehicle_id(node)
		var vehicle_type := _vehicle_type(node)
		var class_id := int(label_catalog.class_id_for_vehicle_type(vehicle_type))
		if class_id < 0:
			continue
		var rect: Rect2 = camera.project_node_rect(node, viewport_size)
		if rect.size.x <= 1.0 or rect.size.y <= 1.0:
			continue
		var object_id := object_registry.register_vehicle(vehicle_id, vehicle_type, class_id)
		var object_color: Color = object_registry.color_for_object_id(object_id)
		_fill_rect(mask, rect, object_color)
		var yolo: PackedFloat32Array = camera.normalized_yolo_rect(rect, viewport_size)
		labels.append({
			"class_id": class_id,
			"vehicle_id": vehicle_id,
			"vehicle_type": vehicle_type,
			"object_id": object_id,
			"x_center": yolo[0],
			"y_center": yolo[1],
			"width": yolo[2],
			"height": yolo[3],
		})

	return {
		"labels": labels,
		"mask": mask,
		"object_metadata": object_registry.metadata(),
	}


func _fill_rect(image: Image, rect: Rect2, color: Color) -> void:
	var clipped := Rect2i(
		int(max(0.0, floor(rect.position.x))),
		int(max(0.0, floor(rect.position.y))),
		int(max(0.0, ceil(rect.size.x))),
		int(max(0.0, ceil(rect.size.y)))
	)
	if clipped.size.x <= 0 or clipped.size.y <= 0:
		return
	image.fill_rect(clipped, color)


func _vehicle_id(node) -> String:
	if node.has_method("sensor_vehicle_id"):
		return str(node.sensor_vehicle_id())
	return str(node.get("vehicle_id"))


func _vehicle_type(node) -> String:
	if node.has_method("sensor_vehicle_type"):
		return str(node.sensor_vehicle_type())
	return str(node.get("vehicle_type"))
