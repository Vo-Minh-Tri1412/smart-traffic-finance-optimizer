@tool
class_name LaneVisualBase
extends Node3D

@export var lane_id := ""
@export var edge_id := ""
@export var lane_width_m := 3.2:
	set(value):
		lane_width_m = max(0.1, value)
		_rebuild_preview_if_needed()
@export var world_scale := 0.02:
	set(value):
		world_scale = max(0.0001, value)
		_rebuild_preview_if_needed()
@export var width_multiplier := 2.4:
	set(value):
		width_multiplier = max(0.05, value)
		_rebuild_preview_if_needed()
@export var min_visual_lane_width := 0.14:
	set(value):
		min_visual_lane_width = max(0.01, value)
		_rebuild_preview_if_needed()
@export var lane_surface_height := 0.022:
	set(value):
		lane_surface_height = value
		_rebuild_preview_if_needed()
@export var lane_material: Material:
	set(value):
		lane_material = value
		_apply_surface_material()
@export var show_center_marking := true:
	set(value):
		show_center_marking = value
		_rebuild_preview_if_needed()
@export var center_marking_width := 0.035:
	set(value):
		center_marking_width = max(0.005, value)
		_rebuild_preview_if_needed()
@export var center_marking_material: Material:
	set(value):
		center_marking_material = value
		_apply_marking_material()
@export_group("Roadside Assets")
@export var show_roadside_props := true:
	set(value):
		show_roadside_props = value
		_rebuild_preview_if_needed()
@export var roadside_prop_entries: Array[Resource] = []:
	set(value):
		roadside_prop_entries = value
		_rebuild_preview_if_needed()
@export var roadside_prop_scenes: Array[PackedScene] = []:
	set(value):
		roadside_prop_scenes = value
		_rebuild_preview_if_needed()
@export var roadside_prop_spacing_m := 120.0:
	set(value):
		roadside_prop_spacing_m = max(10.0, value)
		_rebuild_preview_if_needed()
@export var roadside_prop_offset_m := 5.2:
	set(value):
		roadside_prop_offset_m = value
		_rebuild_preview_if_needed()
@export var roadside_prop_scale := 0.035:
	set(value):
		roadside_prop_scale = max(0.001, value)
		_rebuild_preview_if_needed()
@export var roadside_prop_lane_stride := 8:
	set(value):
		roadside_prop_lane_stride = max(1, value)
		_rebuild_preview_if_needed()
@export var max_roadside_props_per_lane := 1:
	set(value):
		max_roadside_props_per_lane = max(0, value)
		_rebuild_preview_if_needed()
@export var preview_length_m := 24.0:
	set(value):
		preview_length_m = max(1.0, value)
		_rebuild_preview_if_needed()
@export var rebuild_preview := false:
	set(value):
		rebuild_preview = false
		if value:
			_rebuild_visuals()

var _points_m: Array = []
var _mapper = null
var _roadside_prop_count := 0


func _ready() -> void:
	_ensure_children()
	if Engine.is_editor_hint() and _points_m.is_empty():
		_points_m = [
			Vector2(0.0, -preview_length_m / 2.0),
			Vector2(0.0, preview_length_m / 2.0),
		]
		_rebuild_visuals()
	else:
		_apply_surface_material()
		_apply_marking_material()


func configure_from_sumo_lane(
	lane_geometry,
	coordinate_mapper,
	style_entry,
	fallback_lane_material: Material,
	scale: float,
	surface_height: float
) -> void:
	lane_id = String(lane_geometry.lane_id)
	edge_id = String(lane_geometry.edge_id)
	lane_width_m = float(lane_geometry.width_m)
	world_scale = scale
	lane_surface_height = surface_height
	_points_m = (lane_geometry.points as Array).duplicate()
	_mapper = coordinate_mapper
	_apply_style_entry(style_entry, fallback_lane_material)
	name = "Lane_%s" % lane_id
	_rebuild_visuals()


func _apply_style_entry(style_entry, fallback_lane_material: Material) -> void:
	if style_entry != null:
		if style_entry.get("lane_material") is Material:
			lane_material = style_entry.get("lane_material") as Material
		if style_entry.get("lane_marking_material") is Material:
			center_marking_material = style_entry.get("lane_marking_material") as Material
		width_multiplier = float(style_entry.get("width_multiplier"))
		min_visual_lane_width = float(style_entry.get("min_visual_lane_width"))
		show_center_marking = bool(style_entry.get("show_markings"))
		show_roadside_props = bool(style_entry.get("show_roadside_props"))
		if style_entry.get("roadside_prop_entries") is Array:
			roadside_prop_entries.clear()
			for raw_entry in style_entry.get("roadside_prop_entries") as Array:
				if raw_entry is Resource:
					roadside_prop_entries.append(raw_entry as Resource)
		if style_entry.get("roadside_prop_scenes") is Array:
			roadside_prop_scenes.clear()
			for raw_scene in style_entry.get("roadside_prop_scenes") as Array:
				if raw_scene is PackedScene:
					roadside_prop_scenes.append(raw_scene as PackedScene)
		roadside_prop_spacing_m = float(style_entry.get("roadside_prop_spacing_m"))
		roadside_prop_offset_m = float(style_entry.get("roadside_prop_offset_m"))
		roadside_prop_scale = float(style_entry.get("roadside_prop_scale"))
		roadside_prop_lane_stride = int(style_entry.get("roadside_prop_lane_stride"))
		max_roadside_props_per_lane = int(style_entry.get("max_roadside_props_per_lane"))
	if lane_material == null:
		lane_material = fallback_lane_material
	if lane_material == null:
		lane_material = _fallback_material(Color(0.07, 0.072, 0.075))


func _rebuild_preview_if_needed() -> void:
	if Engine.is_editor_hint() and is_inside_tree():
		if _points_m.is_empty():
			_points_m = [
				Vector2(0.0, -preview_length_m / 2.0),
				Vector2(0.0, preview_length_m / 2.0),
			]
		_rebuild_visuals()


func _ensure_children() -> void:
	if get_node_or_null("LaneSurface") == null:
		var surface := MeshInstance3D.new()
		surface.name = "LaneSurface"
		add_child(surface)
		_set_editor_owner(surface)
	if get_node_or_null("CenterMarking") == null:
		var marking := MeshInstance3D.new()
		marking.name = "CenterMarking"
		add_child(marking)
		_set_editor_owner(marking)
	if get_node_or_null("RoadsideProps") == null:
		var props := Node3D.new()
		props.name = "RoadsideProps"
		add_child(props)
		_set_editor_owner(props)


func _set_editor_owner(node: Node) -> void:
	if not Engine.is_editor_hint() or get_tree() == null:
		return
	var edited_root := get_tree().edited_scene_root
	if edited_root != null:
		node.owner = edited_root


func _rebuild_visuals() -> void:
	_ensure_children()
	var surface := get_node_or_null("LaneSurface") as MeshInstance3D
	var marking := get_node_or_null("CenterMarking") as MeshInstance3D
	if surface == null or marking == null:
		return
	surface.mesh = _polyline_strip_mesh(_visual_lane_width_world(), lane_surface_height)
	_apply_surface_material()
	if show_center_marking:
		marking.visible = true
		marking.mesh = _center_line_mesh()
		_apply_marking_material()
	else:
		marking.visible = false
	_build_roadside_props()


func _visual_lane_width_world() -> float:
	return max(min_visual_lane_width, lane_width_m * world_scale * width_multiplier)


func _polyline_strip_mesh(width_world: float, height: float) -> ArrayMesh:
	var mesh := ArrayMesh.new()
	if _points_m.size() < 2:
		return mesh
	var half_width_m: float = max(0.05, width_world / max(0.000001, world_scale) / 2.0)
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var indices := PackedInt32Array()
	for index in range(_points_m.size()):
		var point: Vector2 = _points_m[index] as Vector2
		var normal_2d: Vector2 = _polyline_normal(index)
		var left: Vector2 = point + normal_2d * half_width_m
		var right: Vector2 = point - normal_2d * half_width_m
		vertices.append(_point_to_world(left, height))
		vertices.append(_point_to_world(right, height))
		normals.append(Vector3.UP)
		normals.append(Vector3.UP)
	for index in range(_points_m.size() - 1):
		var base := index * 2
		indices.append(base)
		indices.append(base + 2)
		indices.append(base + 1)
		indices.append(base + 1)
		indices.append(base + 2)
		indices.append(base + 3)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


func _center_line_mesh() -> ArrayMesh:
	return _polyline_strip_mesh(center_marking_width, lane_surface_height + 0.006)


func _build_roadside_props() -> void:
	var props_root := get_node_or_null("RoadsideProps") as Node3D
	if props_root == null:
		return
	_roadside_prop_count = 0
	for child in props_root.get_children():
		props_root.remove_child(child)
		child.queue_free()
	if (
		not show_roadside_props
		or (roadside_prop_entries.is_empty() and roadside_prop_scenes.is_empty())
		or max_roadside_props_per_lane <= 0
		or _points_m.size() < 2
	):
		return
	if _stable_lane_bucket() % roadside_prop_lane_stride != 0:
		return
	var entry = _roadside_prop_entry_for_lane()
	var spacing_m := _roadside_prop_spacing_m(entry)
	if spacing_m <= 0.0:
		return
	var length_m := _polyline_length_m()
	if length_m < spacing_m * 0.45:
		return
	var prop_count: int = min(
		max_roadside_props_per_lane,
		max(1, int(floor(length_m / spacing_m)))
	)
	for index in range(prop_count):
		var fraction := float(index + 1) / float(prop_count + 1)
		var sample := _sample_polyline_at(length_m * fraction)
		var point := sample.get("point") as Vector2
		var tangent := sample.get("tangent") as Vector2
		if tangent.length_squared() <= 0.000001:
			continue
		var normal := Vector2(-tangent.y, tangent.x).normalized()
		var side := 1.0 if (_stable_lane_bucket() + index) % 2 == 0 else -1.0
		var prop_scene := _roadside_prop_scene(entry, index)
		if prop_scene == null:
			continue
		var prop = prop_scene.instantiate()
		if not (prop is Node3D):
			if prop != null:
				prop.queue_free()
			continue
		var prop_node := prop as Node3D
		var wrapper := Node3D.new()
		wrapper.name = "RoadsideProp_%d" % index
		wrapper.position = _point_to_world(
			point + normal * (_lane_half_width_m() + _roadside_prop_offset_m(entry)) * side,
			lane_surface_height + 0.015
		)
		wrapper.rotation.y = atan2(tangent.x, tangent.y)
		wrapper.add_child(prop_node)
		_fit_roadside_prop_to_target_size(wrapper, prop_node, _roadside_prop_target_size_m(entry))
		wrapper.add_to_group("generated_roadside_prop")
		props_root.add_child(wrapper)
		_set_editor_owner(wrapper)
		_roadside_prop_count += 1


func roadside_prop_count() -> int:
	return _roadside_prop_count


func _roadside_prop_entry_for_lane():
	if roadside_prop_entries.is_empty():
		return null
	return roadside_prop_entries[_stable_lane_bucket() % roadside_prop_entries.size()]


func _roadside_prop_scene(entry, index: int) -> PackedScene:
	if entry != null and entry.get("scene") is PackedScene:
		return entry.get("scene") as PackedScene
	if roadside_prop_scenes.is_empty():
		return null
	return roadside_prop_scenes[index % roadside_prop_scenes.size()]


func _roadside_prop_spacing_m(entry) -> float:
	if entry != null:
		return max(0.0, float(entry.get("spacing_m")))
	return roadside_prop_spacing_m


func _roadside_prop_offset_m(entry) -> float:
	if entry != null:
		return max(0.0, float(entry.get("lateral_offset_m")))
	return roadside_prop_offset_m


func _roadside_prop_target_size_m(entry) -> Vector3:
	if entry != null and entry.get("target_size_m") is Vector3:
		return entry.get("target_size_m") as Vector3
	return Vector3.ONE * roadside_prop_scale


func _lane_half_width_m() -> float:
	return max(0.1, lane_width_m * width_multiplier * 0.5)


func _fit_roadside_prop_to_target_size(
	wrapper: Node3D,
	prop_node: Node3D,
	target_size_m: Vector3
) -> void:
	var bounds := _node_local_bounds(prop_node, Transform3D.IDENTITY)
	if not bool(bounds.get("has_bounds", false)):
		wrapper.scale = Vector3.ONE * roadside_prop_scale
		return
	var minimum := bounds.get("minimum", Vector3.ZERO) as Vector3
	var maximum := bounds.get("maximum", Vector3.ZERO) as Vector3
	var raw_size := maximum - minimum
	if min(raw_size.x, min(raw_size.y, raw_size.z)) <= 0.000001:
		wrapper.scale = Vector3.ONE * roadside_prop_scale
		return
	var target_size := target_size_m * world_scale
	wrapper.scale = Vector3(
		target_size.x / raw_size.x,
		target_size.y / raw_size.y,
		target_size.z / raw_size.z
	)
	wrapper.position.y += -minimum.y * wrapper.scale.y


func _node_local_bounds(node: Node, parent_transform: Transform3D) -> Dictionary:
	var result := {
		"has_bounds": false,
		"minimum": Vector3.ZERO,
		"maximum": Vector3.ZERO,
	}
	_collect_node_local_bounds(node, parent_transform, result)
	return result


func _collect_node_local_bounds(node: Node, parent_transform: Transform3D, result: Dictionary) -> void:
	var current_transform := parent_transform
	if node is Node3D:
		current_transform = parent_transform * (node as Node3D).transform
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			for corner in _aabb_corners(mesh_instance.mesh.get_aabb()):
				var point := current_transform * corner
				if not bool(result.get("has_bounds", false)):
					result["has_bounds"] = true
					result["minimum"] = point
					result["maximum"] = point
					continue
				var minimum := result.get("minimum", Vector3.ZERO) as Vector3
				var maximum := result.get("maximum", Vector3.ZERO) as Vector3
				result["minimum"] = minimum.min(point)
				result["maximum"] = maximum.max(point)
	for child in node.get_children():
		_collect_node_local_bounds(child, current_transform, result)


func _aabb_corners(box: AABB) -> Array[Vector3]:
	var position := box.position
	var size := box.size
	return [
		position,
		position + Vector3(size.x, 0.0, 0.0),
		position + Vector3(0.0, size.y, 0.0),
		position + Vector3(0.0, 0.0, size.z),
		position + Vector3(size.x, size.y, 0.0),
		position + Vector3(size.x, 0.0, size.z),
		position + Vector3(0.0, size.y, size.z),
		position + size,
	]


func _polyline_length_m() -> float:
	var total := 0.0
	for index in range(_points_m.size() - 1):
		total += (_points_m[index + 1] as Vector2).distance_to(_points_m[index] as Vector2)
	return total


func _sample_polyline_at(distance_m: float) -> Dictionary:
	var remaining: float = max(0.0, distance_m)
	for index in range(_points_m.size() - 1):
		var start := _points_m[index] as Vector2
		var end := _points_m[index + 1] as Vector2
		var segment := end - start
		var segment_length: float = segment.length()
		if segment_length <= 0.000001:
			continue
		if remaining <= segment_length:
			var ratio: float = remaining / segment_length
			return {
				"point": start.lerp(end, ratio),
				"tangent": segment.normalized(),
			}
		remaining -= segment_length
	var last_start := _points_m[_points_m.size() - 2] as Vector2
	var last_end := _points_m[_points_m.size() - 1] as Vector2
	var last_segment := last_end - last_start
	return {
		"point": last_end,
		"tangent": last_segment.normalized() if last_segment.length_squared() > 0.000001 else Vector2.UP,
	}


func _stable_lane_bucket() -> int:
	var hash_value := 0
	var source := lane_id if not lane_id.is_empty() else edge_id
	for index in range(source.length()):
		hash_value = int((hash_value * 31 + source.unicode_at(index)) % 1000003)
	return abs(hash_value)


func _point_to_world(point: Vector2, height: float) -> Vector3:
	if _mapper != null and _mapper.has_method("sumo_to_world"):
		return _mapper.sumo_to_world(point.x, point.y, height)
	return Vector3(point.x * world_scale, height, point.y * world_scale)


func _polyline_normal(index: int) -> Vector2:
	var current := _points_m[index] as Vector2
	var tangent := Vector2.ZERO
	if index > 0:
		tangent += (current - (_points_m[index - 1] as Vector2)).normalized()
	if index < _points_m.size() - 1:
		tangent += ((_points_m[index + 1] as Vector2) - current).normalized()
	if tangent.length_squared() <= 0.000001:
		if index < _points_m.size() - 1:
			tangent = ((_points_m[index + 1] as Vector2) - current).normalized()
		elif index > 0:
			tangent = (current - (_points_m[index - 1] as Vector2)).normalized()
	if tangent.length_squared() <= 0.000001:
		return Vector2.RIGHT
	tangent = tangent.normalized()
	return Vector2(-tangent.y, tangent.x)


func _apply_surface_material() -> void:
	var surface := get_node_or_null("LaneSurface") as MeshInstance3D
	if surface == null:
		return
	if surface.mesh == null:
		return
	surface.set_surface_override_material(
		0,
		lane_material if lane_material != null else _fallback_material(Color(0.07, 0.072, 0.075))
	)


func _apply_marking_material() -> void:
	var marking := get_node_or_null("CenterMarking") as MeshInstance3D
	if marking == null:
		return
	if marking.mesh == null:
		return
	marking.set_surface_override_material(
		0,
		center_marking_material if center_marking_material != null else _fallback_material(Color(0.95, 0.84, 0.18))
	)


func _fallback_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	return material
