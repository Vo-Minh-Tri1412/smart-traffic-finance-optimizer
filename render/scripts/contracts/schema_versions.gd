extends RefCounted

const SIMULATION_TRACE_FRAME_SCHEMA_VERSION := "simulation_trace_frame.v1"
const GEOMETRY_MANIFEST_SCHEMA_VERSION := "geometry_manifest.v1"
const VEHICLE_TRACE_SCHEMA_VERSION := "vehicle_trace.v2"
const TRAFFIC_LIGHT_TRACE_SCHEMA_VERSION := "traffic_light_trace.v1"
const SEMANTIC_OVERLAY_SCHEMA_VERSION := "semantic_overlay.v2"
const EVENT_TRACE_SCHEMA_VERSION := "event_trace.v1"
const RENDER_RUN_MANIFEST_SCHEMA_VERSION := "render_run_manifest.v1"
const SENSOR_DATASET_MANIFEST_SCHEMA_VERSION := "sensor_dataset_manifest.v1"
const VEHICLE_ASSET_MANIFEST_SCHEMA_VERSION := "vehicle_asset_manifest.v1"
const VEHICLE_ASSET_CATALOG_SCHEMA_VERSION := "vehicle_asset_catalog.v1"
const ZONE_ASSET_CATALOG_SCHEMA_VERSION := "zone_asset_catalog.v1"
const SUMO_NET_XML_SCHEMA_VERSION := "sumo_net_xml.v1"


static func supported_trace_frame_versions() -> Array[String]:
	return [SIMULATION_TRACE_FRAME_SCHEMA_VERSION, VEHICLE_TRACE_SCHEMA_VERSION]


static func render_bridge_schema_versions() -> Dictionary:
	return {
		"geometry_manifest": GEOMETRY_MANIFEST_SCHEMA_VERSION,
		"vehicle_trace": VEHICLE_TRACE_SCHEMA_VERSION,
		"traffic_light_trace": TRAFFIC_LIGHT_TRACE_SCHEMA_VERSION,
		"semantic_overlay": SEMANTIC_OVERLAY_SCHEMA_VERSION,
		"event_trace": EVENT_TRACE_SCHEMA_VERSION,
		"render_run_manifest": RENDER_RUN_MANIFEST_SCHEMA_VERSION,
		"sensor_dataset_manifest": SENSOR_DATASET_MANIFEST_SCHEMA_VERSION,
	}


static func supported_vehicle_asset_manifest_versions() -> Array[String]:
	return [VEHICLE_ASSET_MANIFEST_SCHEMA_VERSION]


static func supported_vehicle_asset_catalog_versions() -> Array[String]:
	return [VEHICLE_ASSET_CATALOG_SCHEMA_VERSION]


static func supported_zone_asset_catalog_versions() -> Array[String]:
	return [ZONE_ASSET_CATALOG_SCHEMA_VERSION]


static func require_supported_version(
	payload: Dictionary,
	field_name: String,
	supported_versions: Array[String],
	errors: Array[String],
	context: String
) -> bool:
	if not payload.has(field_name):
		errors.append("%s missing required %s." % [context, field_name])
		return false
	var version := String(payload.get(field_name, ""))
	if version.is_empty():
		errors.append("%s has empty %s." % [context, field_name])
		return false
	if not supported_versions.has(version):
		errors.append(
			"%s uses unsupported %s=%s. Supported: %s"
			% [context, field_name, version, ", ".join(supported_versions)]
		)
		return false
	return true
