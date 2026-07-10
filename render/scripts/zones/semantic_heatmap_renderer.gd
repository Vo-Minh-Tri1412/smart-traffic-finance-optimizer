@tool
class_name SemanticHeatmapRenderer
extends Node3D

@export var overlay_path := ""
@export var zone_catalog_path := "res://resources/catalogs/ZoneAssetCatalog.tres"
@export var geometry_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var auto_render := false
@export var editor_preview_enabled := false
@export var rebuild_editor_preview := false:
	set(value):
		rebuild_editor_preview = false
		if value and Engine.is_editor_hint() and editor_preview_enabled:
			call_deferred("_auto_render")

@export_group("Heatmap Display")
@export var render_neutral_zones := false
@export var surface_height := 0.055
@export_range(0.0, 1.0, 0.01) var zone_alpha := 0.58
@export var height_step_per_zone_type := 0.002
@export var max_polygons_per_type := 0
@export var max_vertices_per_polygon := 0

var loaded_zone_count := 0
var rendered_polygon_count := 0
var rendered_mesh_count := 0
var skipped_neutral_count := 0
var skipped_polygon_count := 0
var overlay_parse_error_count := 0
var rendered_zone_type_counts: Dictionary = {}
var errors: Array[String] = []

var _zone_catalog = null


func _ready() -> void:
	if Engine.is_editor_hint():
		if editor_preview_enabled and auto_render:
			call_deferred("_auto_render")
		return
	if auto_render:
		call_deferred("_auto_render")


func _auto_render() -> void:
	if not overlay_path.is_empty():
		render_heatmap(overlay_path)


func render_heatmap(path: String) -> bool:
	_clear_generated()
	_reset_summary()
	overlay_path = path
	_load_zone_catalog()

	var overlay := _load_overlay(path)
	if overlay.is_empty():
		return false

	var raw_zones = overlay.get("zones", [])
	if not (raw_zones is Array):
		errors.append("Semantic overlay zones must be an array: %s" % path)
		overlay_parse_error_count += 1
		return false

	var world := get_node_or_null(geometry_world_path)
	var polygons_by_type: Dictionary = {}
	for raw_zone in raw_zones as Array:
		if not (raw_zone is Dictionary):
			overlay_parse_error_count += 1
			continue
		loaded_zone_count += 1
		var zone_data := raw_zone as Dictionary
		var zone_type := _canonical_zone_type(str(zone_data.get("type", zone_data.get("zone_type", "mixed"))))
		if zone_type == "neutral" and not render_neutral_zones:
			skipped_neutral_count += 1
			continue
		var world_polygons := _zone_world_polygons(zone_data, world)
		for polygon in world_polygons:
			if not (polygon is Array):
				skipped_polygon_count += 1
				continue
			var points := _prepare_polygon(polygon as Array)
			if points.size() < 3:
				skipped_polygon_count += 1
				continue
			if max_polygons_per_type > 0 and polygons_by_type.has(zone_type):
				if (polygons_by_type[zone_type] as Array).size() >= max_polygons_per_type:
					skipped_polygon_count += 1
					continue
			if not polygons_by_type.has(zone_type):
				polygons_by_type[zone_type] = []
			(polygons_by_type[zone_type] as Array).append(points)

	var zone_type_index := 0
	for zone_type in _ordered_zone_types(polygons_by_type.keys()):
		var polygons := polygons_by_type[zone_type] as Array
		var mesh := _build_zone_type_mesh(polygons, surface_height + zone_type_index * height_step_per_zone_type)
		if mesh == null:
			continue
		var mesh_instance := MeshInstance3D.new()
		mesh_instance.name = "Heatmap_%s" % zone_type
		mesh_instance.mesh = mesh
		mesh_instance.set_surface_override_material(0, _heatmap_material(zone_type))
		mesh_instance.add_to_group("generated_semantic_heatmap")
		add_child(mesh_instance)
		rendered_mesh_count += 1
		rendered_polygon_count += polygons.size()
		rendered_zone_type_counts[zone_type] = polygons.size()
		zone_type_index += 1

	return rendered_polygon_count > 0 and overlay_parse_error_count == 0


func summary() -> Dictionary:
	return {
		"renderer": "SemanticHeatmapRenderer",
		"overlay_path": overlay_path,
		"zone_catalog_path": zone_catalog_path,
		"loaded_zone_count": loaded_zone_count,
		"rendered_polygon_count": rendered_polygon_count,
		"rendered_mesh_count": rendered_mesh_count,
		"skipped_neutral_count": skipped_neutral_count,
		"skipped_polygon_count": skipped_polygon_count,
		"overlay_parse_error_count": overlay_parse_error_count,
		"rendered_zone_type_counts": rendered_zone_type_counts,
		"errors": errors,
	}


func _reset_summary() -> void:
	loaded_zone_count = 0
	rendered_polygon_count = 0
	rendered_mesh_count = 0
	skipped_neutral_count = 0
	skipped_polygon_count = 0
	overlay_parse_error_count = 0
	rendered_zone_type_counts = {}
	errors.clear()


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_semantic_heatmap"):
			child.queue_free()


func _load_overlay(path: String) -> Dictionary:
	var resolved_path := _resolve_repo_path(path)
	var file := FileAccess.open(resolved_path, FileAccess.READ)
	if file == null:
		errors.append("Semantic overlay not found: %s" % path)
		overlay_parse_error_count += 1
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		errors.append("Semantic overlay must be a JSON object: %s" % path)
		overlay_parse_error_count += 1
		return {}
	return parsed as Dictionary


func _resolve_repo_path(path: String) -> String:
	if not path.begins_with("repo://"):
		return path
	var relative_path := path.trim_prefix("repo://").trim_prefix("/")
	var render_project_path := ProjectSettings.globalize_path("res://").trim_suffix("/")
	return render_project_path.get_base_dir().path_join(relative_path)


func _load_zone_catalog() -> void:
	_zone_catalog = null
	if zone_catalog_path.is_empty():
		return
	var loaded = ResourceLoader.load(zone_catalog_path)
	if loaded != null:
		_zone_catalog = loaded


func _canonical_zone_type(type_id: String) -> String:
	if _zone_catalog != null and _zone_catalog.has_method("canonical_zone_type"):
		return str(_zone_catalog.canonical_zone_type(type_id))
	var canonical := type_id.strip_edges().to_lower().replace("-", "_").replace(" ", "_")
	match canonical:
		"industry", "factory", "manufacturing", "warehouse":
			return "industrial"
		"hospital", "clinic", "medical", "health":
			return "healthcare"
		"school", "university", "college", "campus":
			return "education"
		"market", "retail", "shop", "marketplace":
			return "market_retail"
		"logistics", "port", "depot", "freight":
			return "port_logistics"
		"transport", "station", "bus_station", "terminal":
			return "transport_hub"
		"government", "public", "civic":
			return "public_service"
		"bar", "pub", "club", "entertainment":
			return "nightlife"
		"unknown", "fallback", "generic":
			return "mixed"
		_:
			return canonical


func _ordered_zone_types(zone_types: Array) -> Array[String]:
	var order := [
		"mixed",
		"leisure_tourism",
		"residential",
		"commercial",
		"market_retail",
		"industrial",
		"port_logistics",
		"transport_hub",
		"education",
		"healthcare",
		"public_service",
		"nightlife",
		"gateway",
	]
	var output: Array[String] = []
	for item in order:
		if zone_types.has(item):
			output.append(item)
	for item in zone_types:
		var value := str(item)
		if not output.has(value):
			output.append(value)
	return output


func _zone_world_polygons(zone_data: Dictionary, world: Node) -> Array:
	if world == null:
		return []
	var geometry = zone_data.get("geometry", {})
	if not (geometry is Dictionary):
		return []
	var geometry_data := geometry as Dictionary
	var geometry_type := str(geometry_data.get("type", "")).to_lower()
	var coordinate_system := str(
		geometry_data.get("coordinate_system", zone_data.get("coordinate_system", "lon_lat"))
	).to_lower()
	if geometry_type == "polygon":
		var polygon := _world_polygon_for_coordinates(
			geometry_data.get("coordinates", []),
			world,
			coordinate_system
		)
		if polygon.size() >= 3:
			return [polygon]
		return []
	if geometry_type == "multipolygon":
		var output := []
		var polygon_parts = geometry_data.get("coordinates", [])
		if not (polygon_parts is Array):
			return output
		for raw_part in polygon_parts as Array:
			var part_coordinates := _first_polygon_ring(raw_part)
			var polygon := _world_polygon_for_coordinates(part_coordinates, world, coordinate_system)
			if polygon.size() >= 3:
				output.append(polygon)
		return output
	return []


func _world_polygon_for_coordinates(coordinates, world: Node, coordinate_system: String) -> Array:
	var normalized := coordinate_system.strip_edges().to_lower()
	if normalized in ["sumo_xy", "sumo", "sumo_meters"]:
		if world.has_method("world_polygon_for_sumo_coordinates"):
			var world_polygon = world.world_polygon_for_sumo_coordinates(coordinates, surface_height)
			if world_polygon is Array:
				return world_polygon as Array
		return []
	if world.has_method("world_polygon_for_geo_coordinates"):
		var geo_polygon = world.world_polygon_for_geo_coordinates(coordinates, surface_height)
		if geo_polygon is Array:
			return geo_polygon as Array
	return []


func _first_polygon_ring(raw_part) -> Array:
	if not (raw_part is Array):
		return []
	var part := raw_part as Array
	if part.is_empty():
		return []
	if part[0] is Array:
		var first := part[0] as Array
		if not first.is_empty() and first[0] is Array:
			return first
	return part


func _prepare_polygon(raw_polygon: Array) -> PackedVector3Array:
	var points := PackedVector3Array()
	var stride := _polygon_stride(raw_polygon.size())
	for index in range(0, raw_polygon.size(), stride):
		var point = raw_polygon[index]
		if point is Vector3:
			points.append(point as Vector3)
	if points.size() >= 2 and points[0].distance_squared_to(points[points.size() - 1]) <= 0.000001:
		points.remove_at(points.size() - 1)
	return points


func _polygon_stride(point_count: int) -> int:
	if max_vertices_per_polygon <= 0 or point_count <= max_vertices_per_polygon:
		return 1
	return int(ceil(float(point_count) / float(max_vertices_per_polygon)))


func _build_zone_type_mesh(polygons: Array, y_height: float) -> ArrayMesh:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var indices := PackedInt32Array()
	for raw_polygon in polygons:
		if not (raw_polygon is PackedVector3Array):
			continue
		var polygon := raw_polygon as PackedVector3Array
		var polygon_2d := PackedVector2Array()
		for point in polygon:
			polygon_2d.append(Vector2(point.x, point.z))
		var triangulated := Geometry2D.triangulate_polygon(polygon_2d)
		if triangulated.size() < 3:
			skipped_polygon_count += 1
			continue
		var vertex_offset := vertices.size()
		for point in polygon:
			vertices.append(Vector3(point.x, y_height, point.z))
			normals.append(Vector3.UP)
		for index in triangulated:
			indices.append(vertex_offset + int(index))
	if vertices.is_empty() or indices.is_empty():
		return null
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


func _heatmap_material(zone_type: String) -> StandardMaterial3D:
	var color := _zone_color(zone_type)
	color.a = zone_alpha
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = color
	return material


func _zone_color(zone_type: String) -> Color:
	var entry = _zone_catalog.entry_for_zone_type(zone_type) if _zone_catalog != null else null
	if entry != null:
		var ground_material = entry.get("ground_material")
		if ground_material is BaseMaterial3D:
			var entry_color := (ground_material as BaseMaterial3D).albedo_color
			entry_color.a = zone_alpha
			return entry_color
	match zone_type:
		"residential":
			return Color(0.34, 0.74, 0.42, zone_alpha)
		"commercial":
			return Color(1.0, 0.58, 0.20, zone_alpha)
		"market_retail":
			return Color(1.0, 0.70, 0.28, zone_alpha)
		"education":
			return Color(0.31, 0.62, 1.0, zone_alpha)
		"healthcare":
			return Color(1.0, 0.22, 0.22, zone_alpha)
		"industrial":
			return Color(0.55, 0.39, 0.25, zone_alpha)
		"port_logistics":
			return Color(0.68, 0.32, 0.84, zone_alpha)
		"transport_hub":
			return Color(0.28, 0.80, 0.86, zone_alpha)
		"public_service":
			return Color(0.70, 0.60, 0.90, zone_alpha)
		"nightlife":
			return Color(1.0, 0.35, 0.70, zone_alpha)
		"gateway":
			return Color(0.45, 0.56, 0.72, zone_alpha)
		"mixed":
			return Color(0.67, 0.73, 0.76, zone_alpha)
		_:
			return Color(0.75, 0.75, 0.75, zone_alpha)
