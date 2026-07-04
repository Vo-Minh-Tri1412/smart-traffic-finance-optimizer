@tool
class_name TrafficLightVisualLayer
extends Node3D

const TrafficLightVisualBaseScene := preload("res://scenes/traffic/TrafficLightVisualBase.tscn")

@export var geometry_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var asset_catalog_path := "res://resources/catalogs/TrafficLightAssetCatalog.tres"
@export var auto_render := true
@export var editor_preview_enabled := false
@export var max_visual_lights := 400
@export var visual_height := 0.08
@export var visual_offset_m := 4.2
@export var rebuild_editor_preview := false:
	set(value):
		rebuild_editor_preview = false
		if value and Engine.is_editor_hint() and editor_preview_enabled:
			call_deferred("render_traffic_lights")

var spawned_light_count := 0
var catalog_loaded := false
var errors: Array[String] = []
var _catalog = null


func _ready() -> void:
	if Engine.is_editor_hint():
		if editor_preview_enabled and auto_render:
			call_deferred("render_traffic_lights")
		return
	if auto_render:
		call_deferred("render_traffic_lights")


func render_traffic_lights() -> bool:
	_clear_generated()
	errors.clear()
	spawned_light_count = 0
	_load_catalog()
	var world := get_node_or_null(geometry_world_path)
	if world == null or not world.has_method("traffic_light_junction_world_points"):
		errors.append("TrafficLightVisualLayer needs DistrictReplayWorld geometry.")
		return false
	var raw_lights = world.traffic_light_junction_world_points(max_visual_lights, visual_height)
	if not (raw_lights is Array):
		errors.append("DistrictReplayWorld returned invalid traffic-light geometry.")
		return false
	var entry = _catalog.default_entry() if _catalog != null else null
	for item in raw_lights as Array:
		if not (item is Dictionary):
			continue
		var row := item as Dictionary
		var visual := _create_visual(str(row.get("id", "")), entry)
		if visual == null:
			continue
		var position = row.get("position")
		if position is Vector3:
			visual.position = (position as Vector3) + _offset_for_visual(row)
		visual.add_to_group("generated_traffic_light_visual")
		add_child(visual)
		spawned_light_count += 1
	return spawned_light_count > 0


func summary() -> Dictionary:
	return {
		"traffic_light_visual_count": spawned_light_count,
		"traffic_light_visual_catalog_loaded": catalog_loaded,
		"traffic_light_visual_catalog_path": asset_catalog_path,
		"errors": errors,
	}


func _create_visual(traffic_light_id: String, entry) -> Node3D:
	var scene: PackedScene = TrafficLightVisualBaseScene
	if entry != null and entry.get("visual_scene") is PackedScene:
		scene = entry.get("visual_scene") as PackedScene
	var node = scene.instantiate()
	if not (node is Node3D):
		if node != null:
			node.queue_free()
		return null
	var visual := node as Node3D
	if visual.has_method("configure_traffic_light"):
		visual.configure_traffic_light(traffic_light_id, entry)
	else:
		visual.name = "TrafficLight_%s" % traffic_light_id
	return visual


func _offset_for_visual(row: Dictionary) -> Vector3:
	var angle := float(row.get("angle", 0.0))
	var offset_world := visual_offset_m * float(row.get("world_scale", 0.02))
	return Vector3(cos(angle) * offset_world, 0.0, sin(angle) * offset_world)


func _load_catalog() -> void:
	catalog_loaded = false
	_catalog = null
	if asset_catalog_path.is_empty():
		return
	var loaded := ResourceLoader.load(asset_catalog_path)
	if loaded != null and loaded.has_method("default_entry"):
		_catalog = loaded
		catalog_loaded = true


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_traffic_light_visual"):
			child.queue_free()
