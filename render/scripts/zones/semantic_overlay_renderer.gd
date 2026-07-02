class_name SemanticOverlayRenderer
extends Node3D

const ZoneVisualFactoryScript := preload("res://scripts/assets/zone_visual_factory.gd")

@export var overlay_path := ""
@export var zone_catalog_path := "res://resources/catalogs/ZoneAssetCatalog.tres"
@export var geometry_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var auto_render := true
@export var fallback_ring_radius := 8.0

var zone_factory = null
var spawned_zone_count := 0
var fallback_zone_count := 0
var overlay_parse_error_count := 0
var errors: Array[String] = []


func _ready() -> void:
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
		var zone_node: Node3D = zone_factory.create_zone(zone_data)
		if zone_node == null:
			overlay_parse_error_count += 1
			continue
		zone_node.position = _zone_world_position(zone_data, world, index, zones.size())
		zone_node.add_to_group("generated_zone_visual")
		add_child(zone_node)
		spawned_zone_count += 1
		index += 1

	if zone_factory != null:
		fallback_zone_count = zone_factory.fallback_spawn_count
	return spawned_zone_count > 0 and overlay_parse_error_count == 0


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


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_zone_visual"):
			child.queue_free()
