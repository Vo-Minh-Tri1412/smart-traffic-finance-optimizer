class_name RoadStyleCatalog
extends Resource

const SchemaVersionsScript := preload("res://scripts/contracts/schema_versions.gd")

@export var schema_version := "road_style_catalog.v1"
@export var default_road_role := "default"
@export var entries: Array = []


func canonical_road_role(role: String) -> String:
	return role.strip_edges().to_lower().replace("-", "_").replace(" ", "_")


func entry_for_road_role(role: String):
	var canonical_key := canonical_road_role(role)
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry_obj := raw_entry as Object
		if entry_obj == null:
			continue
		if canonical_road_role(str(entry_obj.get("road_role"))) == canonical_key:
			return entry_obj
	return null


func default_entry():
	var entry = entry_for_road_role(default_road_role)
	if entry != null:
		return entry
	for raw_entry in entries:
		if raw_entry != null:
			return raw_entry as Object
	return null


func material_for_road_role(role: String, material_field: String, fallback_color: Color) -> Material:
	var entry: Object = entry_for_road_role(role)
	if entry == null:
		entry = default_entry()
	if entry != null and entry.get(material_field) is Material:
		return entry.get(material_field) as Material
	var material := StandardMaterial3D.new()
	if entry != null:
		if material_field == "junction_material":
			material.albedo_color = entry.get("junction_color") as Color
		else:
			material.albedo_color = entry.get("lane_color") as Color
	else:
		material.albedo_color = fallback_color
	return material


func registered_road_style_count() -> int:
	var total := 0
	for raw_entry in entries:
		if raw_entry == null:
			continue
		var entry_obj := raw_entry as Object
		if entry_obj == null:
			continue
		if not str(entry_obj.get("road_role")).strip_edges().is_empty():
			total += 1
	return total
