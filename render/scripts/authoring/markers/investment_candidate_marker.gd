@tool
class_name InvestmentCandidateMarker
extends "res://scripts/authoring/markers/authoring_marker_base.gd"

@export var candidate_id := ""
@export var intersection_id := ""
@export var upgrade_type := "AI_TRAFFIC_SIGNAL"
@export var capex_vnd := 500000000.0
@export var annual_maintenance_vnd := 50000000.0
@export var affected_flow_ids: Array[String] = []
@export var caveat := "placeholder; economics team should review"


func _ready() -> void:
	_register_authoring_marker("authoring_investment_candidate")


func to_authoring_dict(context: Dictionary = {}) -> Dictionary:
	var flow_ids := context.get("flow_ids", []) as Array
	var affected := []
	for flow_id in string_array(affected_flow_ids):
		if flow_ids.has(flow_id):
			affected.append(flow_id)
	return {
		"id": candidate_id,
		"intersection_id": intersection_id,
		"upgrade_type": upgrade_type,
		"capex_vnd": capex_vnd,
		"annual_maintenance_vnd": annual_maintenance_vnd,
		"affected_flow_ids": affected,
		"caveat": caveat,
	}
