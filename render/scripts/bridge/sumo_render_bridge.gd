class_name SumoRenderBridge
extends Node3D

const SchemaVersions := preload("res://scripts/contracts/schema_versions.gd")

@export var render_run_manifest_path := ""
@export var geometry_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var trace_replay_controller_path: NodePath = NodePath("../TraceReplayController")
@export var semantic_overlay_renderer_path: NodePath = NodePath("../SemanticOverlayRenderer")
@export var semantic_heatmap_renderer_path: NodePath = NodePath("../SemanticHeatmapRenderer")
@export var preview_layer_toggles_path: NodePath = NodePath("../PreviewLayerToggles")
@export var traffic_light_state_layer_path: NodePath = NodePath("../TrafficLightStateLayer")
@export var sensor_export_layer_path: NodePath = NodePath("")
@export var auto_configure := false

var warnings: Array[String] = []
var loaded_manifest: Dictionary = {}


func _ready() -> void:
	if auto_configure and not render_run_manifest_path.is_empty():
		configure_from_manifest(render_run_manifest_path)


func configure_from_manifest(path: String) -> bool:
	warnings.clear()
	loaded_manifest = _load_json_object(path)
	if loaded_manifest.is_empty():
		return false
	if not _check_schema_version(loaded_manifest, SchemaVersions.RENDER_RUN_MANIFEST_SCHEMA_VERSION, path):
		return false

	_apply_manifest_path("sumo_net", geometry_world_path, "net_path")
	_apply_manifest_path("vehicle_trace", trace_replay_controller_path, "trace_path")
	_apply_manifest_path("semantic_overlay", semantic_overlay_renderer_path, "overlay_path")
	_apply_manifest_path("semantic_overlay", semantic_heatmap_renderer_path, "overlay_path")
	_apply_manifest_path("semantic_overlay", preview_layer_toggles_path, "shared_overlay_path")
	_apply_manifest_path("traffic_light_trace", traffic_light_state_layer_path, "trace_path")
	return true


func bridge_summary() -> Dictionary:
	return {
		"bridge": "SumoRenderBridge",
		"render_run_manifest_path": render_run_manifest_path,
		"render_run_manifest_loaded": not loaded_manifest.is_empty(),
		"supported_contracts": SchemaVersions.render_bridge_schema_versions(),
		"geometry_world_present": get_node_or_null(geometry_world_path) != null,
		"trace_replay_controller_present": get_node_or_null(trace_replay_controller_path) != null,
		"semantic_overlay_renderer_present": get_node_or_null(semantic_overlay_renderer_path) != null,
		"semantic_heatmap_renderer_present": get_node_or_null(semantic_heatmap_renderer_path) != null,
		"preview_layer_toggles_present": get_node_or_null(preview_layer_toggles_path) != null,
		"traffic_light_state_layer_present": get_node_or_null(traffic_light_state_layer_path) != null,
		"sensor_export_layer_present": (
			not sensor_export_layer_path.is_empty()
			and get_node_or_null(sensor_export_layer_path) != null
		),
		"warnings": warnings,
	}


func _load_json_object(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		warnings.append("Render run manifest not found: %s" % path)
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		warnings.append("Render run manifest must be a JSON object: %s" % path)
		return {}
	return parsed as Dictionary


func _check_schema_version(payload: Dictionary, expected_version: String, context: String) -> bool:
	var version := String(payload.get("schema_version", ""))
	if version != expected_version:
		warnings.append(
			"Unsupported render manifest schema in %s: %s. Expected %s"
			% [context, version, expected_version]
		)
		return false
	return true


func _apply_manifest_path(field_name: String, node_path: NodePath, property_name: String) -> void:
	var value := String(loaded_manifest.get(field_name, ""))
	if value.is_empty():
		return
	var node := get_node_or_null(node_path)
	if node == null:
		warnings.append("Cannot apply %s; node missing at %s" % [field_name, node_path])
		return
	node.set(property_name, value)
