extends RefCounted

const SchemaVersionsScript := preload("res://scripts/contracts/schema_versions.gd")
const DEFAULT_FALLBACK_VEHICLE_SCENE := "res://scenes/vehicles/VehicleBase.tscn"

var manifest_path := ""
var manifest_version := ""
var vehicle_scene_paths: Dictionary = {}
var vehicle_scenes: Dictionary = {}
var fallbacks: Dictionary = {}
var scene_cache: Dictionary = {}
var errors: Array[String] = []


func load_manifest(path: String) -> bool:
	manifest_path = path
	errors.clear()
	vehicle_scene_paths.clear()
	vehicle_scenes.clear()
	fallbacks.clear()
	scene_cache.clear()

	if path.is_empty():
		errors.append("Vehicle asset manifest path is empty.")
		return false
	if not FileAccess.file_exists(path):
		errors.append("Vehicle asset manifest not found: %s" % path)
		return false

	var extension := path.get_extension().to_lower()
	if extension == "tres" or extension == "res":
		return _load_resource_catalog(path)

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		errors.append("Cannot open vehicle asset manifest: %s" % path)
		return false

	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		errors.append("Vehicle asset manifest must be a JSON object: %s" % path)
		return false

	var payload := parsed as Dictionary
	manifest_version = String(payload.get("schema_version", payload.get("version", "")))
	if not SchemaVersionsScript.require_supported_version(
		payload,
		"schema_version",
		SchemaVersionsScript.supported_vehicle_asset_manifest_versions(),
		errors,
		"Vehicle asset manifest"
	):
		return false

	var raw_fallbacks = payload.get("fallbacks", {})
	if raw_fallbacks is Dictionary:
		fallbacks = raw_fallbacks as Dictionary

	var raw_vehicle_scenes = payload.get("vehicle_scenes", {})
	if not (raw_vehicle_scenes is Dictionary):
		errors.append("Vehicle asset manifest field vehicle_scenes must be an object.")
		return false

	for raw_key in (raw_vehicle_scenes as Dictionary).keys():
		var canonical_key := canonical_vehicle_type(String(raw_key))
		var raw_value = (raw_vehicle_scenes as Dictionary)[raw_key]
		var scene_path := _extract_scene_path(raw_value)
		if scene_path.is_empty():
			errors.append("Vehicle scene path is empty for vehicle type %s." % canonical_key)
			continue
		vehicle_scene_paths[canonical_key] = scene_path

	return errors.is_empty()


func canonical_vehicle_type(type_id: String) -> String:
	return type_id.strip_edges().to_upper().replace("-", "_").replace(" ", "_")


func scene_path_for_vehicle_type(type_id: String) -> String:
	var canonical_key := canonical_vehicle_type(type_id)
	if vehicle_scene_paths.has(canonical_key):
		return String(vehicle_scene_paths[canonical_key])
	if vehicle_scenes.has(canonical_key):
		var scene := vehicle_scenes[canonical_key] as PackedScene
		if scene != null and not scene.resource_path.is_empty():
			return scene.resource_path
	return fallback_vehicle_scene_path()


func fallback_vehicle_scene_path() -> String:
	return String(fallbacks.get("missing_vehicle_scene", DEFAULT_FALLBACK_VEHICLE_SCENE))


func scene_for_vehicle_type(type_id: String) -> PackedScene:
	var canonical_key := canonical_vehicle_type(type_id)
	if vehicle_scenes.has(canonical_key):
		var cached_scene := vehicle_scenes[canonical_key] as PackedScene
		if cached_scene != null:
			return cached_scene

	var requested_path := scene_path_for_vehicle_type(type_id)
	var scene := _load_scene(requested_path)
	if scene != null:
		return scene

	var fallback_path := fallback_vehicle_scene_path()
	if fallback_path != requested_path:
		scene = _load_scene(fallback_path)
	if scene != null:
		return scene

	push_error("Could not load any vehicle scene for type %s." % type_id)
	return null


func registered_vehicle_type_count() -> int:
	return max(vehicle_scene_paths.size(), vehicle_scenes.size())


func _extract_scene_path(value) -> String:
	if value is String:
		return String(value)
	if value is Dictionary:
		return String((value as Dictionary).get("scene", ""))
	return ""


func _load_scene(path: String) -> PackedScene:
	if path.is_empty():
		return null
	if scene_cache.has(path):
		return scene_cache[path] as PackedScene
	var resource := load(path)
	if resource is PackedScene:
		scene_cache[path] = resource
		return resource as PackedScene
	errors.append("Vehicle scene is missing or not a PackedScene: %s" % path)
	return null


func _load_resource_catalog(path: String) -> bool:
	var resource := load(path)
	if resource == null:
		errors.append("Vehicle asset catalog not found or unreadable: %s" % path)
		return false

	var schema_version := str(resource.get("schema_version"))
	if not SchemaVersionsScript.supported_vehicle_asset_catalog_versions().has(schema_version):
		errors.append(
			"Vehicle asset catalog uses unsupported schema_version=%s. Supported: %s"
			% [schema_version, ", ".join(SchemaVersionsScript.supported_vehicle_asset_catalog_versions())]
		)
		return false
	manifest_version = schema_version

	var fallback_scene = resource.get("fallback_vehicle_scene")
	if fallback_scene is PackedScene:
		fallbacks["missing_vehicle_scene"] = (fallback_scene as PackedScene).resource_path
		scene_cache[(fallback_scene as PackedScene).resource_path] = fallback_scene
	else:
		fallbacks["missing_vehicle_scene"] = DEFAULT_FALLBACK_VEHICLE_SCENE

	var raw_entries = resource.get("entries")
	if not (raw_entries is Array):
		errors.append("Vehicle asset catalog entries must be an array: %s" % path)
		return false

	var entries := raw_entries as Array
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var vehicle_type := str(raw_entry.get("vehicle_type"))
		var scene = raw_entry.get("vehicle_scene")
		if vehicle_type.strip_edges().is_empty():
			errors.append("Vehicle asset catalog has an entry with an empty vehicle_type.")
			continue
		if not (scene is PackedScene):
			errors.append("Vehicle asset catalog entry for %s has no PackedScene." % vehicle_type)
			continue
		var canonical_key := canonical_vehicle_type(vehicle_type)
		vehicle_scenes[canonical_key] = scene
		var scene_path := (scene as PackedScene).resource_path
		if not scene_path.is_empty():
			vehicle_scene_paths[canonical_key] = scene_path
			scene_cache[scene_path] = scene

	return errors.is_empty()
