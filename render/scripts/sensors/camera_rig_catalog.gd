class_name CameraRigCatalog
extends Resource

@export var schema_version := "camera_rig_catalog.v1"
@export var entries: Array = []


func enabled_entries() -> Array:
	var result: Array = []
	for raw_entry in entries:
		if raw_entry == null:
			continue
		if bool(raw_entry.get("enabled")):
			result.append(raw_entry)
	return result


func entry_count() -> int:
	return entries.size()


func enabled_count() -> int:
	return enabled_entries().size()
