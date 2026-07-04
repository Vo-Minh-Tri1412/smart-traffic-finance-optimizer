@tool
class_name SemanticOverlayRenderer
extends Node3D

const ZoneVisualFactoryScript := preload("res://scripts/assets/zone_visual_factory.gd")

@export var overlay_path := ""
@export var zone_catalog_path := "res://resources/catalogs/ZoneAssetCatalog.tres"
@export var geometry_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var auto_render := true
@export var editor_preview_enabled := false
@export var show_zone_labels := false
@export var rebuild_editor_preview := false:
	set(value):
		rebuild_editor_preview = false
		if value and Engine.is_editor_hint() and editor_preview_enabled:
			call_deferred("_auto_render")
@export var fallback_ring_radius := 8.0

var zone_factory = null
var spawned_zone_count := 0
var fallback_zone_count := 0
var overlay_parse_error_count := 0
var errors: Array[String] = []


func _ready() -> void:
	if Engine.is_editor_hint():
		if editor_preview_enabled and auto_render:
			call_deferred("_auto_render")
		return
	if auto_render:
		call_deferred("_auto_render")


func _auto_render() -> void:
	if not overlay_path.is_empty():
		render_overlay(overlay_path)


func render_overlay(path: String) -> bool:
	_clear_generated()
	errors.clear()
	overlay_parse_error_count = 0
	spawned_zone_count = 0
	fallback_zone_count = 0

	var overlay := _load_overlay(path)
	if overlay.is_empty():
		return false

	zone_factory = ZoneVisualFactoryScript.new()
	if not zone_factory.configure(zone_catalog_path):
		for error in zone_factory.errors:
			push_warning(error)

	var raw_zones = overlay.get("zones", [])
	if not (raw_zones is Array):
		errors.append("Semantic overlay zones must be an array: %s" % path)
		return false

	var world := get_node_or_null(geometry_world_path)
	var zones := raw_zones as Array
	var index := 0
	for raw_zone in zones:
		if not (raw_zone is Dictionary):
			overlay_parse_error_count += 1
			continue
		var zone_data := raw_zone as Dictionary
		var world_polygons := _zone_world_polygons(zone_data, world)
		if world_polygons.is_empty():
			if not _spawn_zone_visual(zone_data, [], world, index, zones.size()):
				overlay_parse_error_count += 1
		else:
			var part_index := 0
			for raw_polygon in world_polygons:
				if not (raw_polygon is Array):
					continue
				var world_polygon := raw_polygon as Array
				if world_polygon.size() < 3:
					continue
				var part_data := zone_data.duplicate(true)
				part_data["id"] = "%s_part_%d" % [str(zone_data.get("id", "zone")), part_index + 1]
				if not _spawn_zone_visual(part_data, world_polygon, world, index, zones.size()):
					overlay_parse_error_count += 1
				part_index += 1
		index += 1

	if zone_factory != null:
		fallback_zone_count = zone_factory.fallback_spawn_count
	return spawned_zone_count > 0 and overlay_parse_error_count == 0


func _spawn_zone_visual(
	zone_data: Dictionary,
	world_polygon: Array,
	world: Node,
	index: int,
	total: int
) -> bool:
	var zone_node: Node3D = zone_factory.create_zone(zone_data)
	if zone_node == null:
		return false
	var zone_position := _zone_world_position(zone_data, world, index, total)
	if not world_polygon.is_empty():
		zone_position = _polygon_centroid(world_polygon)
		if str(zone_data.get("type", "")) == "neutral":
			zone_position.y = 0.004
		else:
			zone_position.y = 0.012
	zone_node.position = zone_position
	zone_node.set("show_label", show_zone_labels)
	if (
		world != null
		and zone_node.has_method("configure_world_units_per_meter")
		and world.get("world_scale") != null
	):
		zone_node.configure_world_units_per_meter(float(world.get("world_scale")))
	if not world_polygon.is_empty() and zone_node.has_method("configure_zone_polygon"):
		zone_node.configure_zone_polygon(_local_polygon(world_polygon, zone_position))
	zone_node.add_to_group("generated_zone_visual")
	add_child(zone_node)
	spawned_zone_count += 1
	return true


func summary() -> Dictionary:
	return {
		"spawned_zone_count": spawned_zone_count,
		"fallback_zone_count": fallback_zone_count,
		"overlay_parse_error_count": overlay_parse_error_count,
		"zone_catalog_path": zone_catalog_path,
		"zone_asset_catalog_loaded": (
			zone_factory.catalog_loaded() if zone_factory != null else false
		),
		"registered_zone_type_count": (
			zone_factory.registered_zone_type_count() if zone_factory != null else 0
		),
	}


func _load_overlay(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		errors.append("Semantic overlay not found: %s" % path)
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		errors.append("Semantic overlay must be a JSON object: %s" % path)
		overlay_parse_error_count += 1
		return {}
	return parsed as Dictionary


func _zone_world_position(zone_data: Dictionary, world: Node, index: int, total: int) -> Vector3:
	if world != null and world.has_method("world_position_for_edge_ids"):
		var anchor_edges = zone_data.get("anchor_edges", [])
		var anchor_position = world.world_position_for_edge_ids(anchor_edges)
		if anchor_position is Vector3:
			return (anchor_position as Vector3) + Vector3(0.0, 0.15, 0.0)
	var angle := TAU * float(index) / float(max(1, total))
	return Vector3(cos(angle) * fallback_ring_radius, 0.15, sin(angle) * fallback_ring_radius)


func _zone_world_polygons(zone_data: Dictionary, world: Node) -> Array:
	if world == null or not world.has_method("world_polygon_for_geo_coordinates"):
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
			var part_coordinates = _first_polygon_ring(raw_part)
			var polygon := _world_polygon_for_coordinates(part_coordinates, world, coordinate_system)
			if polygon.size() >= 3:
				output.append(polygon)
		return output
	return []


func _world_polygon_for_coordinates(coordinates, world: Node, coordinate_system: String) -> Array:
	var normalized := coordinate_system.strip_edges().to_lower()
	if normalized in ["sumo_xy", "sumo", "sumo_meters"]:
		if world.has_method("world_polygon_for_sumo_coordinates"):
			var world_polygon = world.world_polygon_for_sumo_coordinates(coordinates, 0.04)
			if world_polygon is Array:
				return world_polygon as Array
		return []
	var geo_polygon = world.world_polygon_for_geo_coordinates(coordinates, 0.04)
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


func _polygon_centroid(points: Array) -> Vector3:
	if points.is_empty():
		return Vector3.ZERO
	var total := Vector3.ZERO
	var count := 0
	for point in points:
		if point is Vector3:
			total += point as Vector3
			count += 1
	if count == 0:
		return Vector3.ZERO
	var center := total / float(count)
	center.y = 0.04
	return center


func _local_polygon(points: Array, origin: Vector3) -> Array:
	var output: Array[Vector3] = []
	for point in points:
		if not (point is Vector3):
			continue
		var value := point as Vector3
		output.append(Vector3(value.x - origin.x, 0.0, value.z - origin.z))
	return output


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_zone_visual"):
			child.queue_free()
