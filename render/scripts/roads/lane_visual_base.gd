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
	surface.set_surface_override_material(
		0,
		lane_material if lane_material != null else _fallback_material(Color(0.07, 0.072, 0.075))
	)


func _apply_marking_material() -> void:
	var marking := get_node_or_null("CenterMarking") as MeshInstance3D
	if marking == null:
		return
	marking.set_surface_override_material(
		0,
		center_marking_material if center_marking_material != null else _fallback_material(Color(0.95, 0.84, 0.18))
	)


func _fallback_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	return material
