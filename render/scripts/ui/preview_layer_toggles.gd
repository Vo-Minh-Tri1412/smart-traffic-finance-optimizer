@tool
class_name PreviewLayerToggles
extends Node

@export var show_roads := true:
	set(value):
		show_roads = value
		_request_apply()
@export var show_zones := true:
	set(value):
		show_zones = value
		_request_apply()
@export var show_zone_heatmap := true:
	set(value):
		show_zone_heatmap = value
		_request_apply()
@export var show_zone_assets := false:
	set(value):
		show_zone_assets = value
		_request_apply()
@export var show_vehicles := true:
	set(value):
		show_vehicles = value
		_request_apply()
@export var show_traffic_lights := true:
	set(value):
		show_traffic_lights = value
		_request_apply()
@export_enum("visual", "heatmap", "both") var zone_render_mode := "visual":
	set(value):
		zone_render_mode = value
		show_zone_heatmap = zone_render_mode in ["heatmap", "both"]
		show_zone_assets = zone_render_mode in ["visual", "both"]
		_request_apply()
@export_file("*.json") var shared_overlay_path := "":
	set(value):
		shared_overlay_path = value
		_request_apply()
@export var auto_rebuild_visible_layers := false
@export var rebuild_visible_layers_now := false:
	set(value):
		rebuild_visible_layers_now = false
		if value:
			_apply()
			_rebuild_visible_layers()

@export var road_layer_path: NodePath = NodePath("../DistrictReplayWorld")
@export var zone_layer_path: NodePath = NodePath("../SemanticOverlayRenderer")
@export var heatmap_layer_path: NodePath = NodePath("../SemanticHeatmapRenderer")
@export var vehicle_layer_path: NodePath = NodePath("../TraceReplayController")
@export var traffic_light_state_layer_path: NodePath = NodePath("../TrafficLightStateLayer")
@export var traffic_light_visual_layer_path: NodePath = NodePath("../TrafficLightVisualLayer")


func _ready() -> void:
	call_deferred("_apply")
	if not Engine.is_editor_hint() and auto_rebuild_visible_layers:
		call_deferred("_rebuild_visible_layers")


func _request_apply() -> void:
	if is_inside_tree():
		call_deferred("_apply")


func _apply() -> void:
	_set_visible(road_layer_path, show_roads)
	_apply_shared_overlay_path()
	_set_visible(zone_layer_path, show_zones and show_zone_assets)
	_set_visible(heatmap_layer_path, show_zones and show_zone_heatmap)
	_set_visible(vehicle_layer_path, show_vehicles)
	_set_visible(traffic_light_state_layer_path, show_traffic_lights)
	_set_visible(traffic_light_visual_layer_path, show_traffic_lights)


func _set_visible(path: NodePath, value: bool) -> void:
	var node := get_node_or_null(path)
	if node is CanvasItem:
		(node as CanvasItem).visible = value
	elif node is Node3D:
		(node as Node3D).visible = value


func _apply_shared_overlay_path() -> void:
	if shared_overlay_path.strip_edges().is_empty():
		return
	for path in [zone_layer_path, heatmap_layer_path]:
		var node := get_node_or_null(path)
		if node != null:
			node.set("overlay_path", shared_overlay_path)


func _rebuild_visible_layers() -> void:
	_rebuild_world_if_needed()
	if show_zones and show_zone_heatmap:
		_rebuild_heatmap_layer()
	if show_zones and show_zone_assets:
		_rebuild_zone_asset_layer()


func _rebuild_world_if_needed() -> void:
	var world := get_node_or_null(road_layer_path)
	if world == null:
		return
	if world.has_method("has_geometry_bounds") and world.has_geometry_bounds():
		return
	var net_path := str(world.get("net_path"))
	var spec_path := str(world.get("spec_path"))
	if not net_path.is_empty() and world.has_method("build_from_sumo_net"):
		world.build_from_sumo_net(net_path)
	elif not spec_path.is_empty() and world.has_method("build_from_spec"):
		world.build_from_spec(spec_path)


func _rebuild_heatmap_layer() -> void:
	var heatmap := get_node_or_null(heatmap_layer_path)
	if heatmap == null or not heatmap.has_method("render_heatmap"):
		return
	var path := str(heatmap.get("overlay_path"))
	if not path.is_empty():
		heatmap.render_heatmap(path)


func _rebuild_zone_asset_layer() -> void:
	var zone_layer := get_node_or_null(zone_layer_path)
	if zone_layer == null or not zone_layer.has_method("render_overlay"):
		return
	var path := str(zone_layer.get("overlay_path"))
	if not path.is_empty():
		zone_layer.render_overlay(path)
