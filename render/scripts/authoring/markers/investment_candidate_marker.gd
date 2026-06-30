@tool
class_name InvestmentCandidateMarker
extends Node3D

@export var candidate_id := ""
@export var intersection_id := ""
@export var upgrade_type := "AI_TRAFFIC_SIGNAL"
@export var capex_vnd := 500000000.0
@export var annual_maintenance_vnd := 50000000.0
@export var affected_flow_ids: Array[String] = []
@export var caveat := "placeholder; economics team should review"


func _ready() -> void:
	add_to_group("authoring_investment_candidate")
