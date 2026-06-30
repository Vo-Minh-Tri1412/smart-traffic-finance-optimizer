extends RefCounted

const SIMULATION_TRACE_FRAME_SCHEMA_VERSION := "simulation_trace_frame.v1"
const VEHICLE_ASSET_MANIFEST_SCHEMA_VERSION := "vehicle_asset_manifest.v1"
const SUMO_NET_XML_SCHEMA_VERSION := "sumo_net_xml.v1"


static func supported_trace_frame_versions() -> Array[String]:
	return [SIMULATION_TRACE_FRAME_SCHEMA_VERSION]


static func supported_vehicle_asset_manifest_versions() -> Array[String]:
	return [VEHICLE_ASSET_MANIFEST_SCHEMA_VERSION]


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
