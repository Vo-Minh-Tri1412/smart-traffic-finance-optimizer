@tool
class_name RoadVisualRoot
extends Node3D

@export var edge_id := ""
@export var road_role := "default"
@export var lane_ids: PackedStringArray = []


func configure(sumo_edge_id: String, role: String, lanes: Array) -> void:
	edge_id = sumo_edge_id
	road_role = role
	lane_ids = PackedStringArray()
	for lane_id in lanes:
		lane_ids.append(String(lane_id))
	name = "Road_%s" % edge_id


func lane_parent() -> Node3D:
	var existing := get_node_or_null("LaneVisuals")
	if existing is Node3D:
		return existing as Node3D
	var lane_visuals := Node3D.new()
	lane_visuals.name = "LaneVisuals"
	add_child(lane_visuals)
	if Engine.is_editor_hint() and get_tree() != null:
		lane_visuals.owner = get_tree().edited_scene_root
	return lane_visuals


func attachment_parent() -> Node3D:
	var existing := get_node_or_null("Attachments")
	if existing is Node3D:
		return existing as Node3D
	var attachments := Node3D.new()
	attachments.name = "Attachments"
	add_child(attachments)
	if Engine.is_editor_hint() and get_tree() != null:
		attachments.owner = get_tree().edited_scene_root
	return attachments
