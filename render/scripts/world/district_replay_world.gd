@tool
class_name DistrictReplayWorld
extends Node3D

const CoordinateMapperScript := preload("res://scripts/replay/coordinate_mapper.gd")
const SumoNetGeometryDataScript := preload("res://scripts/world/sumo_net_geometry_data.gd")
const RoadSceneBuilderScript := preload("res://scripts/roads/road_scene_builder.gd")

@export var spec_path := ""
@export var net_path := ""
@export var road_style_catalog_path := "res://resources/catalogs/RoadStyleCatalog.tres"
@export var world_scale := 0.02
@export var sumo_meters_per_spec_unit := 1000.0
@export var road_width := 1.6
@export var lane_width_m := 3.2
@export var enable_large_map_lod := true
@export var max_visual_lanes := 3200
@export var max_visual_junctions := 1200
@export var visual_lane_width_multiplier := 2.4
@export var min_visual_lane_width := 0.14
@export var min_visual_junction_radius := 0.32
@export var max_visual_junction_radius := 2.4
@export var lane_surface_height := 0.022
@export var junction_surface_height := 0.018
@export var editor_preview_enabled := false
@export var rebuild_editor_preview := false:
	set(value):
		rebuild_editor_preview = false
		if value and Engine.is_editor_hint() and editor_preview_enabled:
			call_deferred("_build_editor_preview")
@export var render_lane_as_scenes := true
@export var render_lane_mesh_strips := true
@export var road_visual_root_scene: PackedScene = preload("res://scenes/roads/RoadVisualRoot.tscn")
@export var lane_visual_scene: PackedScene = preload("res://scenes/roads/LaneVisualBase.tscn")

var intersection_positions: Dictionary = {}
var road_count := 0
var intersection_count := 0
var lane_count := 0
var rendered_lane_count := 0
var rendered_junction_count := 0
var rendered_lane_mesh_count := 0
var rendered_lane_segment_count := 0
var min_lane_width_m := 0.0
var max_lane_width_m := 0.0
var average_lane_width_m := 0.0
var _spec_center := Vector2.ZERO
var _sumo_geometry = null
var _sumo_bounds_min := Vector2.ZERO
var _sumo_bounds_max := Vector2.ZERO
var _has_sumo_geometry := false
var _mapper = null
var _lane_material: StandardMaterial3D = null
var _junction_material: StandardMaterial3D = null
var _road_style_catalog = null
var _road_scene_builder: Object = null
var _road_visual_roots: Dictionary = {}


func _ready() -> void:
	if Engine.is_editor_hint():
		if editor_preview_enabled:
			call_deferred("_build_editor_preview")
		return
	if not net_path.is_empty():
		build_from_sumo_net(net_path)
	elif not spec_path.is_empty():
		build_from_spec(spec_path)


func _build_editor_preview() -> void:
	if not Engine.is_editor_hint() or not editor_preview_enabled:
		return
	if not net_path.is_empty():
		build_from_sumo_net(net_path)
	elif not spec_path.is_empty():
		build_from_spec(spec_path)


func build_from_spec(path: String) -> bool:
	_clear_generated()
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_warning("District spec not found for Godot world: %s" % path)
		return false
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("District spec is not a JSON object: %s" % path)
		return false
	var spec := parsed as Dictionary
	_build_intersections(spec.get("intersections", []))
	_build_roads(spec.get("roads", []))
	return true


func build_from_sumo_net(path: String) -> bool:
	_clear_generated()
	_sumo_geometry = SumoNetGeometryDataScript.new()
	if not _sumo_geometry.load_xml(path):
		for error in _sumo_geometry.errors:
			push_warning(error)
		return false

	_configure_sumo_bounds(_sumo_geometry)
	_fit_ground_to_sumo_bounds()
	lane_count = _sumo_geometry.lane_count()
	road_count = _sumo_geometry.edge_to_lanes.size()
	intersection_count = _sumo_geometry.junction_count()
	rendered_lane_count = 0
	rendered_junction_count = 0
	rendered_lane_mesh_count = 0
	rendered_lane_segment_count = 0
	min_lane_width_m = 0.0
	max_lane_width_m = 0.0
	average_lane_width_m = 0.0
	var width_summary: Dictionary = _sumo_geometry.lane_width_summary()
	min_lane_width_m = float(width_summary.get("min_lane_width_m", 0.0))
	max_lane_width_m = float(width_summary.get("max_lane_width_m", 0.0))
	average_lane_width_m = float(width_summary.get("average_lane_width_m", 0.0))
	_load_road_style_catalog()
	_apply_default_road_style()

	var lane_stride := _render_stride(_sumo_geometry.lanes.size(), max_visual_lanes)
	for index in range(_sumo_geometry.lanes.size()):
		if _should_render_index(index, lane_stride):
			_build_sumo_lane(_sumo_geometry.lanes[index])
	var junction_stride := _render_stride(_sumo_geometry.junctions.size(), max_visual_junctions)
	for index in range(_sumo_geometry.junctions.size()):
		if _should_render_index(index, junction_stride):
			_build_sumo_junction(_sumo_geometry.junctions[index])
	return true


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_world_object"):
			child.queue_free()
	intersection_positions.clear()
	road_count = 0
	intersection_count = 0
	lane_count = 0
	rendered_lane_count = 0
	rendered_junction_count = 0
	rendered_lane_mesh_count = 0
	rendered_lane_segment_count = 0
	min_lane_width_m = 0.0
	max_lane_width_m = 0.0
	average_lane_width_m = 0.0
	_sumo_geometry = null
	_sumo_bounds_min = Vector2.ZERO
	_sumo_bounds_max = Vector2.ZERO
	_has_sumo_geometry = false
	_mapper = null
	_lane_material = null
	_junction_material = null
	_road_style_catalog = null
	_road_scene_builder = null
	_road_visual_roots.clear()


func _build_intersections(intersections: Array) -> void:
	_spec_center = _intersection_center(intersections)
	for item in intersections:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var row := item as Dictionary
		var intersection_id := String(row.get("id", ""))
		if intersection_id.is_empty():
			continue
		var sumo_x := float(row.get("x", 0.0)) * sumo_meters_per_spec_unit
		var sumo_y := float(row.get("y", 0.0)) * sumo_meters_per_spec_unit
		var position := Vector3(
			(sumo_x - _spec_center.x) * world_scale,
			0.05,
			(sumo_y - _spec_center.y) * world_scale
		)
		intersection_positions[intersection_id] = position
		var marker := MeshInstance3D.new()
		marker.name = "Intersection_%s" % intersection_id
		marker.mesh = _cylinder_mesh(1.9, 0.12)
		marker.position = position
		marker.set_surface_override_material(0, _material(Color(0.08, 0.09, 0.10)))
		marker.add_to_group("generated_world_object")
		add_child(marker)
		intersection_count += 1


func _build_roads(roads: Array) -> void:
	for item in roads:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var row := item as Dictionary
		var from_id := String(row.get("from", ""))
		var to_id := String(row.get("to", ""))
		if not intersection_positions.has(from_id) or not intersection_positions.has(to_id):
			continue
		var start := intersection_positions[from_id] as Vector3
		var end := intersection_positions[to_id] as Vector3
		var midpoint := (start + end) / 2.0
		var direction := end - start
		var length: float = direction.length()
		if length < 0.1:
			length = 0.1
		var lanes: int = int(row.get("lanes", 1))
		if lanes < 1:
			lanes = 1

		var road := MeshInstance3D.new()
		road.name = "Road_%s" % String(row.get("id", "unknown"))
		var mesh := BoxMesh.new()
		mesh.size = Vector3(road_width * lanes, 0.04, length)
		road.mesh = mesh
		road.position = Vector3(midpoint.x, 0.0, midpoint.z)
		road.rotation.y = atan2(direction.x, direction.z)
		road.set_surface_override_material(0, _material(Color(0.18, 0.18, 0.18)))
		road.add_to_group("generated_world_object")
		add_child(road)
		road_count += 1


func _cylinder_mesh(radius: float, height: float) -> CylinderMesh:
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 24
	return mesh


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	return material


func _load_road_style_catalog() -> void:
	if road_style_catalog_path.is_empty():
		return
	var loaded = ResourceLoader.load(road_style_catalog_path)
	if loaded != null:
		_road_style_catalog = loaded


func _apply_default_road_style() -> void:
	if _road_style_catalog != null and _road_style_catalog.has_method("material_for_road_role"):
		var lane_material = _road_style_catalog.material_for_road_role(
			"default",
			"lane_material",
			Color(0.07, 0.072, 0.075)
		)
		var junction_material = _road_style_catalog.material_for_road_role(
			"default",
			"junction_material",
			Color(0.035, 0.036, 0.04)
		)
		if lane_material is StandardMaterial3D:
			_lane_material = lane_material as StandardMaterial3D
		elif lane_material is Material:
			_lane_material = _material(Color(0.07, 0.072, 0.075))
		if junction_material is StandardMaterial3D:
			_junction_material = junction_material as StandardMaterial3D
		elif junction_material is Material:
			_junction_material = _material(Color(0.035, 0.036, 0.04))
		var default_entry = _road_style_catalog.default_entry()
		if default_entry != null:
			visual_lane_width_multiplier = float(default_entry.get("width_multiplier"))
			min_visual_lane_width = float(default_entry.get("min_visual_lane_width"))
	if _lane_material == null:
		_lane_material = _material(Color(0.07, 0.072, 0.075))
	if _junction_material == null:
		_junction_material = _material(Color(0.035, 0.036, 0.04))


func _build_sumo_lane(lane_geometry) -> void:
	if render_lane_as_scenes and _build_sumo_lane_scene(lane_geometry):
		return
	if render_lane_mesh_strips:
		_build_sumo_lane_strip(lane_geometry)
		return
	_build_sumo_lane_segment_boxes(lane_geometry)


func _build_sumo_lane_scene(lane_geometry) -> bool:
	var builder: Object = _road_builder()
	if builder == null:
		return false
	var style_entry = _style_entry_for_lane(lane_geometry)
	var lane_node: Node3D = builder.build_lane_visual(
		lane_geometry,
		_mapper,
		style_entry,
		_lane_material if _lane_material != null else _material(Color(0.07, 0.072, 0.075)),
		world_scale,
		lane_surface_height
	)
	if lane_node == null:
		return false
	var road_root := _road_root_for_lane(lane_geometry, style_entry)
	var lane_parent: Node3D = builder.lane_parent_for(road_root)
	lane_parent.add_child(lane_node)
	rendered_lane_count += 1
	rendered_lane_mesh_count += 1
	rendered_lane_segment_count += max(0, (lane_geometry.points as Array).size() - 1)
	return true


func _road_builder() -> Object:
	if _road_scene_builder == null:
		_road_scene_builder = RoadSceneBuilderScript.new()
		_road_scene_builder.configure(lane_visual_scene, road_visual_root_scene)
	return _road_scene_builder


func _style_entry_for_lane(_lane_geometry):
	if _road_style_catalog != null and _road_style_catalog.has_method("default_entry"):
		return _road_style_catalog.default_entry()
	return null


func _road_root_for_lane(lane_geometry, style_entry) -> Node3D:
	var edge_id := String(lane_geometry.edge_id)
	if _road_visual_roots.has(edge_id):
		return _road_visual_roots[edge_id] as Node3D
	var lane_ids := []
	if _sumo_geometry != null and _sumo_geometry.edge_to_lanes.has(edge_id):
		lane_ids = (_sumo_geometry.edge_to_lanes[edge_id] as Array).duplicate()
	var root: Node3D = _road_builder().build_road_root(edge_id, lane_ids, style_entry)
	root.add_to_group("generated_world_object")
	add_child(root)
	_road_visual_roots[edge_id] = root
	return root


func _build_sumo_lane_segment_boxes(lane_geometry) -> void:
	var lane_material := _lane_material if _lane_material != null else _material(Color(0.08, 0.08, 0.085))
	var lane_id := String(lane_geometry.lane_id)
	var points: Array = lane_geometry.points
	var lane_width := float(lane_geometry.width_m)
	for index in range(points.size() - 1):
		var start := points[index] as Vector2
		var end := points[index + 1] as Vector2
		var direction := end - start
		var length_m := direction.length()
		if length_m < 0.1:
			continue
		var midpoint := (start + end) / 2.0
		var lane_mesh := MeshInstance3D.new()
		lane_mesh.name = "Lane_%s_%d" % [lane_id, index]
		var mesh := BoxMesh.new()
		mesh.size = Vector3(
			max(min_visual_lane_width, lane_width * world_scale * visual_lane_width_multiplier),
			0.04,
			length_m * world_scale
		)
		lane_mesh.mesh = mesh
		lane_mesh.position = _mapper.sumo_to_world(midpoint.x, midpoint.y, 0.02)
		lane_mesh.rotation.y = atan2(direction.x, direction.y)
		lane_mesh.set_surface_override_material(0, lane_material)
		lane_mesh.add_to_group("generated_world_object")
		add_child(lane_mesh)
		rendered_lane_segment_count += 1
	rendered_lane_count += 1
	rendered_lane_mesh_count += 1


func _build_sumo_lane_strip(lane_geometry) -> void:
	var mesh: ArrayMesh = _lane_strip_mesh(lane_geometry)
	if mesh == null:
		return
	var lane_mesh := MeshInstance3D.new()
	lane_mesh.name = "Lane_%s" % String(lane_geometry.lane_id)
	lane_mesh.mesh = mesh
	lane_mesh.set_surface_override_material(
		0,
		_lane_material if _lane_material != null else _material(Color(0.07, 0.072, 0.075))
	)
	lane_mesh.add_to_group("generated_world_object")
	add_child(lane_mesh)
	rendered_lane_count += 1
	rendered_lane_mesh_count += 1
	rendered_lane_segment_count += max(0, (lane_geometry.points as Array).size() - 1)


func _lane_strip_mesh(lane_geometry) -> ArrayMesh:
	var points: Array = lane_geometry.points
	if points.size() < 2:
		return null
	var width_world: float = max(
		min_visual_lane_width,
		float(lane_geometry.width_m) * world_scale * visual_lane_width_multiplier
	)
	var half_width_m: float = max(0.05, width_world / max(0.000001, world_scale) / 2.0)
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var indices := PackedInt32Array()
	for index in range(points.size()):
		var point := points[index] as Vector2
		var normal_2d := _polyline_normal(points, index)
		var left := point + normal_2d * half_width_m
		var right := point - normal_2d * half_width_m
		vertices.append(_mapper.sumo_to_world(left.x, left.y, lane_surface_height))
		vertices.append(_mapper.sumo_to_world(right.x, right.y, lane_surface_height))
		normals.append(Vector3.UP)
		normals.append(Vector3.UP)
	for index in range(points.size() - 1):
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
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


func _polyline_normal(points: Array, index: int) -> Vector2:
	var current := points[index] as Vector2
	var tangent := Vector2.ZERO
	if index > 0:
		tangent += (current - (points[index - 1] as Vector2)).normalized()
	if index < points.size() - 1:
		tangent += ((points[index + 1] as Vector2) - current).normalized()
	if tangent.length_squared() <= 0.000001:
		if index < points.size() - 1:
			tangent = ((points[index + 1] as Vector2) - current).normalized()
		elif index > 0:
			tangent = (current - (points[index - 1] as Vector2)).normalized()
	if tangent.length_squared() <= 0.000001:
		return Vector2.RIGHT
	tangent = tangent.normalized()
	return Vector2(-tangent.y, tangent.x)


func _build_sumo_junction(junction) -> void:
	if (junction.shape_points as Array).size() >= 3:
		var junction_mesh: ArrayMesh = _junction_shape_mesh(junction)
		if junction_mesh != null:
			var polygon := MeshInstance3D.new()
			polygon.name = "Junction_%s" % String(junction.junction_id)
			polygon.mesh = junction_mesh
			polygon.set_surface_override_material(
				0,
				_junction_material if _junction_material != null else _material(Color(0.025, 0.025, 0.03))
			)
			polygon.add_to_group("generated_world_object")
			add_child(polygon)
			rendered_junction_count += 1
			return
	var marker := MeshInstance3D.new()
	marker.name = "Junction_%s" % String(junction.junction_id)
	marker.mesh = _cylinder_mesh(_junction_radius(junction), 0.08)
	marker.position = _mapper.sumo_to_world(junction.point.x, junction.point.y, 0.05)
	marker.set_surface_override_material(
		0,
		_junction_material if _junction_material != null else _material(Color(0.025, 0.025, 0.03))
	)
	marker.add_to_group("generated_world_object")
	add_child(marker)
	rendered_junction_count += 1


func _junction_shape_mesh(junction) -> ArrayMesh:
	var shape: Array = junction.shape_points
	if shape.size() < 3:
		return null
	var polygon := PackedVector2Array()
	for point in shape:
		var value := point as Vector2
		polygon.append(value)
	var triangulated := Geometry2D.triangulate_polygon(polygon)
	if triangulated.size() < 3:
		return null
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	for point in shape:
		var value := point as Vector2
		vertices.append(_mapper.sumo_to_world(value.x, value.y, junction_surface_height))
		normals.append(Vector3.UP)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = triangulated
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


func _junction_radius(junction) -> float:
	var shape: Array = junction.shape_points
	if shape.size() < 2:
		return 0.22
	var min_value := shape[0] as Vector2
	var max_value := shape[0] as Vector2
	for point in shape:
		var value := point as Vector2
		min_value.x = min(min_value.x, value.x)
		min_value.y = min(min_value.y, value.y)
		max_value.x = max(max_value.x, value.x)
		max_value.y = max(max_value.y, value.y)
	return clamp(
		(max_value - min_value).length() * world_scale / 2.0,
		min_visual_junction_radius,
		max_visual_junction_radius
	)


func _configure_sumo_bounds(geometry) -> void:
	_sumo_bounds_min = geometry.bounds_min
	_sumo_bounds_max = geometry.bounds_max
	_mapper = CoordinateMapperScript.new()
	_mapper.configure(_sumo_bounds_min, _sumo_bounds_max, world_scale)
	_has_sumo_geometry = true


func _fit_ground_to_sumo_bounds() -> void:
	var ground := get_node_or_null("Ground")
	if not (ground is MeshInstance3D):
		return
	var ground_mesh = (ground as MeshInstance3D).mesh
	if not (ground_mesh is PlaneMesh):
		return
	var width: float = abs(_sumo_bounds_max.x - _sumo_bounds_min.x) * world_scale
	var depth: float = abs(_sumo_bounds_max.y - _sumo_bounds_min.y) * world_scale
	(ground_mesh as PlaneMesh).size = Vector2(max(90.0, width * 1.12), max(90.0, depth * 1.12))


func has_geometry_bounds() -> bool:
	return _has_sumo_geometry


func get_geometry_bounds_min() -> Vector2:
	return _sumo_bounds_min


func get_geometry_bounds_max() -> Vector2:
	return _sumo_bounds_max


func distance_to_nearest_lane_m(x: float, y: float) -> float:
	if _sumo_geometry == null:
		return 0.0
	return float(_sumo_geometry.distance_to_nearest_lane_m(Vector2(x, y)))


func world_position_for_edge_id(edge_id: String) -> Variant:
	if _sumo_geometry == null or _mapper == null:
		return null
	var center = _sumo_geometry.center_for_edge(edge_id)
	if center is Vector2:
		return _mapper.sumo_to_world((center as Vector2).x, (center as Vector2).y, 0.18)
	return null


func world_position_for_edge_ids(edge_ids) -> Variant:
	if not (edge_ids is Array):
		return null
	var total := Vector3.ZERO
	var count := 0
	var edge_id_values := edge_ids as Array
	for edge_id in edge_id_values:
		var point = world_position_for_edge_id(String(edge_id))
		if point is Vector3:
			total += point as Vector3
			count += 1
	if count == 0:
		return null
	return total / float(count)


func world_position_for_lon_lat(lon: float, lat: float, height := 0.04) -> Variant:
	if _sumo_geometry == null or _mapper == null:
		return null
	if not _sumo_geometry.has_method("sumo_point_for_lon_lat"):
		return null
	var sumo_point = _sumo_geometry.sumo_point_for_lon_lat(lon, lat)
	if not (sumo_point is Vector2):
		return null
	var point := sumo_point as Vector2
	return _mapper.sumo_to_world(point.x, point.y, height)


func world_polygon_for_geo_coordinates(coordinates, height := 0.04) -> Array:
	var output: Array[Vector3] = []
	if not (coordinates is Array):
		return output
	for raw_point in coordinates as Array:
		if not (raw_point is Array):
			continue
		var values := raw_point as Array
		if values.size() < 2:
			continue
		var world_position = world_position_for_lon_lat(
			float(values[0]),
			float(values[1]),
			height
		)
		if world_position is Vector3:
			output.append(world_position as Vector3)
	return output


func geometry_data_model() -> String:
	return "SumoNetGeometryData" if _sumo_geometry != null else "spec_fallback"


func lane_render_model() -> String:
	if render_lane_as_scenes:
		return "SUMO lane scene builder"
	return "SUMO lane-width mesh strips" if render_lane_mesh_strips else "segment box fallback"


func road_style_model() -> String:
	return "RoadStyleCatalog" if _road_style_catalog != null else "hard-coded fallback"


func _render_stride(total_count: int, max_count: int) -> int:
	if not enable_large_map_lod:
		return 1
	if max_count <= 0 or total_count <= max_count:
		return 1
	return int(ceil(float(total_count) / float(max_count)))


func _should_render_index(index: int, stride: int) -> bool:
	return stride <= 1 or index % stride == 0


func _intersection_center(intersections: Array) -> Vector2:
	var has_value := false
	var min_value := Vector2.ZERO
	var max_value := Vector2.ZERO
	for item in intersections:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var row := item as Dictionary
		var point := Vector2(
			float(row.get("x", 0.0)) * sumo_meters_per_spec_unit,
			float(row.get("y", 0.0)) * sumo_meters_per_spec_unit
		)
		if not has_value:
			min_value = point
			max_value = point
			has_value = true
		else:
			min_value.x = min(min_value.x, point.x)
			min_value.y = min(min_value.y, point.y)
			max_value.x = max(max_value.x, point.x)
			max_value.y = max(max_value.y, point.y)
	return (min_value + max_value) / 2.0 if has_value else Vector2.ZERO
