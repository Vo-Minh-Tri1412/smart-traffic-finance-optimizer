class_name LabelMappingEntry
extends Resource

@export var vehicle_type := ""
@export var class_id := 0
@export var label_name := ""
@export var vehicle_type_aliases: Array[String] = []


func canonical_vehicle_type(value: String = "") -> String:
	var source := vehicle_type if value.is_empty() else value
	return source.strip_edges().to_upper().replace("-", "_").replace(" ", "_")
