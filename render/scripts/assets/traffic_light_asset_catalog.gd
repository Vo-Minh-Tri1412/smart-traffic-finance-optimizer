class_name TrafficLightAssetCatalog
extends Resource

@export var schema_version := "traffic_light_asset_catalog.v1"
@export var default_role := "default"
@export var entries: Array = []


func entry_for_role(role: String):
	var canonical_key := _canonical(role)
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry := raw_entry as Object
		if entry == null:
			continue
		if _canonical(str(entry.get("role"))) == canonical_key:
			return entry
	return null


func default_entry():
	var entry = entry_for_role(default_role)
	if entry != null:
		return entry
	for raw_entry in entries:
		if raw_entry != null:
			return raw_entry as Object
	return null


func registered_entry_count() -> int:
	var total := 0
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry := raw_entry as Object
		if entry != null and not str(entry.get("role")).strip_edges().is_empty():
			total += 1
	return total


func _canonical(value: String) -> String:
	return value.strip_edges().to_lower().replace("-", "_").replace(" ", "_")
