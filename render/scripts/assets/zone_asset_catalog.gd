@tool
class_name ZoneAssetCatalog
extends Resource

const SchemaVersionsScript := preload("res://scripts/contracts/schema_versions.gd")

@export var schema_version := SchemaVersionsScript.ZONE_ASSET_CATALOG_SCHEMA_VERSION
@export var fallback_zone_scene: PackedScene
@export var entries: Array = []


func canonical_zone_type(type_id: String) -> String:
	var canonical := type_id.strip_edges().to_lower().replace("-", "_").replace(" ", "_")
	match canonical:
		"house", "housing", "home", "homes", "residence", "residences", "res":
			return "residential"
		"commerce", "office", "offices", "service", "services", "business":
			return "commercial"
		"market", "retail", "shop", "shops", "shopping", "marketplace":
			return "market_retail"
		"school", "university", "college", "campus", "kindergarten", "education_zone", "edu":
			return "education"
		"hospital", "clinic", "medical", "health", "health_care", "emergency":
			return "healthcare"
		"industry", "factory", "manufacturing", "warehouse":
			return "industrial"
		"logistics", "port", "depot", "freight", "container", "harbor":
			return "port_logistics"
		"transport", "transit", "station", "bus_station", "terminal", "hub":
			return "transport_hub"
		"government", "civic", "administrative", "public", "public_office":
			return "public_service"
		"bar", "pub", "club", "entertainment", "restaurant_night":
			return "nightlife"
		"entry", "exit", "gate", "logistics_gateway":
			return "gateway"
		"unknown", "generic", "fallback":
			return "mixed"
		_:
			return canonical


func entry_for_zone_type(type_id: String):
	var canonical_key := canonical_zone_type(type_id)
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry_obj := raw_entry as Object
		if entry_obj == null:
			continue
		if canonical_zone_type(str(entry_obj.get("zone_type"))) == canonical_key:
			return entry_obj
	return null


func scene_for_zone_type(type_id: String) -> PackedScene:
	var entry: Object = entry_for_zone_type(type_id)
	if entry != null and entry.get("zone_scene") is PackedScene:
		return entry.get("zone_scene") as PackedScene
	return fallback_zone_scene


func registered_zone_type_count() -> int:
	var total := 0
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry_obj := raw_entry as Object
		if entry_obj == null:
			continue
		if not str(entry_obj.get("zone_type")).strip_edges().is_empty() and entry_obj.get("zone_scene") is PackedScene:
			total += 1
	return total
