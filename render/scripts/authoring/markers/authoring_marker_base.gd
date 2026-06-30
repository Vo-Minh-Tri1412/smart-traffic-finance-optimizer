@tool
class_name AuthoringMarkerBase
extends Node3D


func _register_authoring_marker(specific_group: String) -> void:
	add_to_group("authoring_marker")
	if not specific_group.is_empty():
		add_to_group(specific_group)


func to_authoring_dict(_context: Dictionary = {}) -> Dictionary:
	return {}


func to_authoring_rows(context: Dictionary = {}) -> Array:
	var row := to_authoring_dict(context)
	if row.is_empty():
		return []
	return [row]


func display_name_or(default_id: String, display_name: String) -> String:
	if display_name.strip_edges().is_empty():
		return default_id
	return display_name


func string_array(raw: Variant) -> Array:
	var output := []
	if raw is Array:
		for item in raw:
			output.append(String(item))
	return output


func global_position_km() -> Vector2:
	return Vector2(round3(global_position.x / 1000.0), round3(global_position.z / 1000.0))


func round3(value: float) -> float:
	return snappedf(value, 0.001)


func normalized_number_map(raw: Dictionary, fallback: Dictionary) -> Dictionary:
	var values := {}
	for key in raw.keys():
		var value := float(raw[key])
		if value > 0.0:
			values[String(key)] = value
	if values.is_empty():
		for key in fallback.keys():
			values[String(key)] = float(fallback[key])

	var total := 0.0
	for value in values.values():
		total += float(value)
	if total <= 0.0:
		return {}

	var output := {}
	for key in values.keys():
		output[String(key)] = round3(float(values[key]) / total)
	var correction := 1.0 - _sum_values(output)
	if not output.is_empty():
		var first_key := String(output.keys()[0])
		output[first_key] = round3(float(output[first_key]) + correction)
	return output


func _sum_values(values: Dictionary) -> float:
	var total := 0.0
	for value in values.values():
		total += float(value)
	return total
