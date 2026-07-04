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
@export var show_vehicles := true:
	set(value):
		show_vehicles = value
		_request_apply()
@export var show_traffic_lights := true:
	set(value):
		show_traffic_lights = value
		_request_apply()

@export var road_layer_path: NodePath = NodePath("../DistrictReplayWorld")
@export var zone_layer_path: NodePath = NodePath("../SemanticOverlayRenderer")
@export var vehicle_layer_path: NodePath = NodePath("../TraceReplayController")
@export var traffic_light_state_layer_path: NodePath = NodePath("../TrafficLightStateLayer")
@export var traffic_light_visual_layer_path: NodePath = NodePath("../TrafficLightVisualLayer")


func _ready() -> void:
	call_deferred("_apply")


func _request_apply() -> void:
	if is_inside_tree():
		call_deferred("_apply")


func _apply() -> void:
	_set_visible(road_layer_path, show_roads)
	_set_visible(zone_layer_path, show_zones)
	_set_visible(vehicle_layer_path, show_vehicles)
	_set_visible(traffic_light_state_layer_path, show_traffic_lights)
	_set_visible(traffic_light_visual_layer_path, show_traffic_lights)


func _set_visible(path: NodePath, value: bool) -> void:
	var node := get_node_or_null(path)
	if node is CanvasItem:
		(node as CanvasItem).visible = value
	elif node is Node3D:
		(node as Node3D).visible = value
