class_name DetectionCamera3D
extends Camera3D

@export var sensor_id := "CAM_DEFAULT"
@export var role := "intersection"
@export var split := "train"
@export var output_size := Vector2i(640, 640)
@export var capture_interval_seconds := 1.0
@export var calibration_schema_version := ""
@export var coordinate_system := ""


func _ready() -> void:
	add_to_group("detection_camera")


func configure_from_entry(entry) -> void:
	if entry == null:
		return
	sensor_id = str(entry.get("sensor_id"))
	role = str(entry.get("role"))
	split = str(entry.get("split"))
	output_size = entry.get("image_size") as Vector2i
	capture_interval_seconds = float(entry.get("capture_interval_seconds"))
	position = entry.get("position") as Vector3
	rotation_degrees = entry.get("rotation_degrees") as Vector3
	fov = float(entry.get("fov_degrees"))
	name = _safe_node_name(sensor_id)


func configure_from_calibration(entry: Dictionary, geometry_world: Node = null) -> void:
	sensor_id = String(entry.get("camera_id", ""))
	role = String(entry.get("role", "intersection"))
	calibration_schema_version = String(entry.get("schema_version", "camera_calibration.v1"))
	coordinate_system = "sumo_xy_meters_z_up"
	var image = entry.get("image_size", {})
	if image is Dictionary:
		output_size = Vector2i(
			int((image as Dictionary).get("width", 640)),
			int((image as Dictionary).get("height", 640))
		)
	var intrinsics = entry.get("intrinsics", {})
	if intrinsics is Dictionary and output_size.y > 0:
		var fy := float((intrinsics as Dictionary).get("fy", 0.0))
		if fy > 0.0:
			fov = rad_to_deg(2.0 * atan(float(output_size.y) / (2.0 * fy)))
	capture_interval_seconds = float(entry.get("capture_interval_seconds", 1.0))
	var rotation = entry.get("rotation_degrees", {})
	if rotation is Dictionary:
		rotation_degrees = Vector3(
			float((rotation as Dictionary).get("pitch", 0.0)),
			90.0 - float((rotation as Dictionary).get("yaw", 0.0)),
			float((rotation as Dictionary).get("roll", 0.0))
		)
	var position_values = entry.get("position_m", [])
	if position_values is Array and (position_values as Array).size() == 3:
		var values := position_values as Array
		var mapped_position = null
		if geometry_world != null and geometry_world.has_method("world_position_for_sumo_coordinate"):
			mapped_position = geometry_world.world_position_for_sumo_coordinate(
				float(values[0]),
				float(values[1]),
				float(values[2])
			)
		if mapped_position is Vector3:
			position = mapped_position as Vector3
		else:
			position = Vector3(float(values[0]), float(values[2]), float(values[1]))
	name = _safe_node_name(sensor_id)


func project_node_rect(node: Node3D, viewport_size: Vector2i) -> Rect2:
	if node == null or viewport_size.x <= 0 or viewport_size.y <= 0:
		return Rect2()

	var bounds := _world_bounds_for_node(node)
	if bounds.is_empty():
		return Rect2()

	var min_point := Vector2(INF, INF)
	var max_point := Vector2(-INF, -INF)
	var visible_corner_count := 0
	for point in bounds:
		if is_position_behind(point):
			continue
		var projected := unproject_position(point)
		min_point.x = min(min_point.x, projected.x)
		min_point.y = min(min_point.y, projected.y)
		max_point.x = max(max_point.x, projected.x)
		max_point.y = max(max_point.y, projected.y)
		visible_corner_count += 1

	if visible_corner_count == 0:
		return Rect2()

	var viewport_rect := Rect2(Vector2.ZERO, Vector2(viewport_size))
	var rect := Rect2(min_point, max_point - min_point).intersection(viewport_rect)
	if rect.size.x <= 1.0 or rect.size.y <= 1.0:
		return Rect2()
	return rect


func normalized_yolo_rect(rect: Rect2, viewport_size: Vector2i) -> PackedFloat32Array:
	var x_center := (rect.position.x + rect.size.x / 2.0) / float(viewport_size.x)
	var y_center := (rect.position.y + rect.size.y / 2.0) / float(viewport_size.y)
	var width := rect.size.x / float(viewport_size.x)
	var height := rect.size.y / float(viewport_size.y)
	return PackedFloat32Array([x_center, y_center, width, height])


func _world_bounds_for_node(node: Node3D) -> Array[Vector3]:
	var combined: AABB
	var has_bounds := false
	for mesh in _mesh_instances(node):
		var local_aabb := mesh.get_aabb()
		var corners := _aabb_corners(local_aabb)
		for corner in corners:
			var world_point := mesh.global_transform * corner
			if not has_bounds:
				combined = AABB(world_point, Vector3.ZERO)
				has_bounds = true
			else:
				combined = combined.expand(world_point)
	if not has_bounds:
		var fallback_size := Vector3(1.4, 0.8, 2.2)
		combined = AABB(node.global_position - fallback_size / 2.0, fallback_size)
	return _aabb_corners(combined)


func _mesh_instances(root: Node) -> Array[MeshInstance3D]:
	var meshes: Array[MeshInstance3D] = []
	if root is MeshInstance3D:
		meshes.append(root as MeshInstance3D)
	for child in root.get_children():
		meshes.append_array(_mesh_instances(child))
	return meshes


func _aabb_corners(aabb: AABB) -> Array[Vector3]:
	var p := aabb.position
	var s := aabb.size
	return [
		p,
		p + Vector3(s.x, 0.0, 0.0),
		p + Vector3(0.0, s.y, 0.0),
		p + Vector3(0.0, 0.0, s.z),
		p + Vector3(s.x, s.y, 0.0),
		p + Vector3(s.x, 0.0, s.z),
		p + Vector3(0.0, s.y, s.z),
		p + s,
	]


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_").replace(" ", "_")
