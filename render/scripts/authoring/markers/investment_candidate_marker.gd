@tool
class_name InvestmentCandidateMarker
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var candidate_id := ""
@export_node_path("Node3D") var intersection_path: NodePath = NodePath("")
@export var intersection_id := ""
@export var upgrade_type := "AI_TRAFFIC_SIGNAL"
@export var capex_vnd := 500000000.0
@export var annual_maintenance_vnd := 50000000.0
@export var affected_flow_paths: Array[NodePath] = []
@export var affected_flow_ids: Array[String] = []
@export var caveat := "placeholder; economics team should review"


func _ready() -> void:
	_register_authoring_marker("authoring_investment_candidate")


func to_authoring_dict(context: Dictionary = {}) -> Dictionary:
	var flow_ids := context.get("flow_ids", []) as Array
	var resolved_intersection_id := node_id_from_path(intersection_path, "intersection_id")
	if resolved_intersection_id.is_empty():
		resolved_intersection_id = intersection_id
	var affected := []
	var candidate_flow_ids := ids_from_node_paths(affected_flow_paths, "flow_id")
	if candidate_flow_ids.is_empty():
		candidate_flow_ids = string_array(affected_flow_ids)
	for flow_id in candidate_flow_ids:
		if flow_ids.has(flow_id):
			affected.append(flow_id)
	return {
		"id": candidate_id,
		"intersection_id": resolved_intersection_id,
		"upgrade_type": upgrade_type,
		"capex_vnd": capex_vnd,
		"annual_maintenance_vnd": annual_maintenance_vnd,
		"affected_flow_ids": affected,
		"caveat": caveat,
	}
