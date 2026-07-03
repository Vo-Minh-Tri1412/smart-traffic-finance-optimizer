class_name VehicleAssetCatalog
extends Resource

const SchemaVersionsScript := preload("res://scripts/contracts/schema_versions.gd")

@export var schema_version := SchemaVersionsScript.VEHICLE_ASSET_CATALOG_SCHEMA_VERSION
@export var fallback_vehicle_scene: PackedScene
@export var entries: Array = []


func canonical_vehicle_type(type_id: String) -> String:
	return type_id.strip_edges().to_upper().replace("-", "_").replace(" ", "_")


func entry_for_vehicle_type(type_id: String):
	var canonical_key := canonical_vehicle_type(type_id)
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry_obj := raw_entry as Object
		if entry_obj == null:
			continue
		if canonical_vehicle_type(str(entry_obj.get("vehicle_type"))) == canonical_key:
			return entry_obj
	return null


func scene_for_vehicle_type(type_id: String) -> PackedScene:
	var entry: Object = entry_for_vehicle_type(type_id)
	if entry != null and entry.get("vehicle_scene") is PackedScene:
		return entry.get("vehicle_scene") as PackedScene
	return fallback_vehicle_scene


func visual_asset_scene_for_vehicle_type(type_id: String) -> PackedScene:
	var entry: Object = entry_for_vehicle_type(type_id)
	if entry != null and entry.get("visual_asset_scene") is PackedScene:
		return entry.get("visual_asset_scene") as PackedScene
	return null


func visual_asset_scale_for_vehicle_type(type_id: String) -> Vector3:
	var entry: Object = entry_for_vehicle_type(type_id)
	if entry != null and entry.get("visual_asset_scale") is Vector3:
		return entry.get("visual_asset_scale") as Vector3
	return Vector3.ONE


func visual_asset_offset_for_vehicle_type(type_id: String) -> Vector3:
	var entry: Object = entry_for_vehicle_type(type_id)
	if entry != null and entry.get("visual_asset_offset") is Vector3:
		return entry.get("visual_asset_offset") as Vector3
	return Vector3.ZERO


func visual_asset_rotation_degrees_for_vehicle_type(type_id: String) -> Vector3:
	var entry: Object = entry_for_vehicle_type(type_id)
	if entry != null and entry.get("visual_asset_rotation_degrees") is Vector3:
		return entry.get("visual_asset_rotation_degrees") as Vector3
	return Vector3.ZERO


func hide_base_body_for_vehicle_type(type_id: String) -> bool:
	var entry: Object = entry_for_vehicle_type(type_id)
	if entry != null:
		return bool(entry.get("hide_base_body_when_visual_asset_exists"))
	return true


func registered_vehicle_type_count() -> int:
	var total := 0
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry_obj := raw_entry as Object
		if entry_obj == null:
			continue
		if not str(entry_obj.get("vehicle_type")).strip_edges().is_empty() and entry_obj.get("vehicle_scene") is PackedScene:
			total += 1
	return total
