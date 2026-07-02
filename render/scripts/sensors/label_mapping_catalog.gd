class_name LabelMappingCatalog
extends Resource

@export var schema_version := "label_mapping_catalog.v1"
@export var entries: Array = []
@export var fallback_class_id := -1
@export var fallback_class_name := "unknown"


func canonical_vehicle_type(value: String) -> String:
	return value.strip_edges().to_upper().replace("-", "_").replace(" ", "_")


func entry_for_vehicle_type(vehicle_type: String):
	var canonical_key := canonical_vehicle_type(vehicle_type)
	for raw_entry in entries:
		if raw_entry == null:
			continue
		if canonical_vehicle_type(str(raw_entry.get("vehicle_type"))) == canonical_key:
			return raw_entry
		var aliases = raw_entry.get("vehicle_type_aliases")
		if aliases is Array:
			for alias in aliases:
				if canonical_vehicle_type(str(alias)) == canonical_key:
					return raw_entry
	return null


func class_id_for_vehicle_type(vehicle_type: String) -> int:
	var entry = entry_for_vehicle_type(vehicle_type)
	if entry == null:
		return fallback_class_id
	return int(entry.get("class_id"))


func class_name_for_vehicle_type(vehicle_type: String) -> String:
	var entry = entry_for_vehicle_type(vehicle_type)
	if entry == null:
		return fallback_class_name
	return str(entry.get("label_name"))


func class_names() -> Array[String]:
	var pairs: Array = []
	for raw_entry in entries:
		if raw_entry == null:
			continue
		pairs.append({
			"id": _entry_class_id(raw_entry),
			"name": str(raw_entry.get("label_name")),
		})
	pairs.sort_custom(func(left, right): return left["id"] < right["id"])
	var names: Array[String] = []
	for pair in pairs:
		names.append(str(pair["name"]))
	return names


func registered_class_count() -> int:
	return class_names().size()


func _entry_class_id(entry) -> int:
	var value = entry.get("class_id")
	if typeof(value) == TYPE_INT:
		return value
	if typeof(value) == TYPE_FLOAT:
		return int(value)
	if typeof(value) == TYPE_STRING and str(value).is_valid_int():
		return str(value).to_int()
	return -1
