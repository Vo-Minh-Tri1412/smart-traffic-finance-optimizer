class_name RoadSceneBuilder
extends RefCounted

const LaneVisualBaseScript := preload("res://scripts/roads/lane_visual_base.gd")
const RoadVisualRootScript := preload("res://scripts/roads/road_visual_root.gd")

var default_lane_scene: PackedScene
var default_road_root_scene: PackedScene


func configure(lane_scene: PackedScene, road_root_scene: PackedScene) -> void:
	default_lane_scene = lane_scene
	default_road_root_scene = road_root_scene


func build_road_root(edge_id: String, lane_ids: Array, style_entry) -> Node3D:
	var root_scene := _scene_from_style(style_entry, "road_root_scene", default_road_root_scene)
	var root: Node3D
	if root_scene != null:
		root = root_scene.instantiate() as Node3D
	else:
		root = RoadVisualRootScript.new()
	if root == null:
		root = Node3D.new()
	if root.has_method("configure"):
		root.configure(edge_id, _road_role(style_entry), lane_ids)
	else:
		root.name = "Road_%s" % edge_id
	root.add_to_group("generated_world_object")
	return root


func build_lane_visual(
	lane_geometry,
	coordinate_mapper,
	style_entry,
	fallback_lane_material: Material,
	world_scale: float,
	lane_surface_height: float
) -> Node3D:
	var lane_scene := _scene_from_style(style_entry, "lane_visual_scene", default_lane_scene)
	var lane_node: Node3D
	if lane_scene != null:
		lane_node = lane_scene.instantiate() as Node3D
	else:
		lane_node = LaneVisualBaseScript.new()
	if lane_node == null:
		return null
	if lane_node.has_method("configure_from_sumo_lane"):
		lane_node.configure_from_sumo_lane(
			lane_geometry,
			coordinate_mapper,
			style_entry,
			fallback_lane_material,
			world_scale,
			lane_surface_height
		)
	else:
		lane_node.name = "Lane_%s" % String(lane_geometry.lane_id)
	lane_node.add_to_group("generated_world_object")
	return lane_node


func lane_parent_for(root: Node3D) -> Node3D:
	if root.has_method("lane_parent"):
		return root.lane_parent()
	return root


func _scene_from_style(style_entry, field_name: String, fallback_scene: PackedScene) -> PackedScene:
	if style_entry != null and style_entry.get(field_name) is PackedScene:
		return style_entry.get(field_name) as PackedScene
	return fallback_scene


func _road_role(style_entry) -> String:
	if style_entry != null:
		return String(style_entry.get("road_role"))
	return "default"
