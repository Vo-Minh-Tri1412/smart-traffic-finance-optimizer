class_name SumoNetGeometryData
extends RefCounted

const SumoLaneGeometryScript := preload("res://scripts/world/sumo_lane_geometry.gd")
const SumoJunctionGeometryScript := preload("res://scripts/world/sumo_junction_geometry.gd")

var lanes: Array = []
var junctions: Array = []
var bounds_min := Vector2.ZERO
var bounds_max := Vector2.ZERO
var has_bounds := false
var errors: Array[String] = []


func load_xml(path: String) -> bool:
	lanes.clear()
	junctions.clear()
	errors.clear()
	has_bounds = false
	bounds_min = Vector2.ZERO
	bounds_max = Vector2.ZERO

	var parser := XMLParser.new()
	var open_error := parser.open(path)
	if open_error != OK:
		errors.append("SUMO net file not found for Godot world: %s" % path)
		return false

	var all_points: Array[Vector2] = []
	while parser.read() == OK:
		if parser.get_node_type() != XMLParser.NODE_ELEMENT:
			continue
		var node_name := parser.get_node_name()
		if node_name == "lane":
			_parse_lane(parser, all_points)
		elif node_name == "junction":
			_parse_junction(parser, all_points)

	if all_points.is_empty():
		errors.append("SUMO net file has no lane or junction geometry: %s" % path)
		return false

	_configure_bounds(all_points)
	return errors.is_empty()


func lane_count() -> int:
	return lanes.size()


func junction_count() -> int:
	return junctions.size()


func distance_to_nearest_lane_m(point: Vector2) -> float:
	if lanes.is_empty():
		return 0.0
	var best := INF
	for lane in lanes:
		best = min(best, float(lane.distance_to_point_m(point)))
	return best


func _parse_lane(parser: XMLParser, all_points: Array[Vector2]) -> void:
	var shape := _attr(parser, "shape")
	var lane_id := _attr(parser, "id")
	if shape.is_empty():
		return
	var points := _parse_shape(shape)
	if points.size() < 2:
		return
	var lane = SumoLaneGeometryScript.new()
	lane.configure(lane_id, points)
	if not lane.is_valid():
		return
	lanes.append(lane)
	for point in points:
		all_points.append(point)


func _parse_junction(parser: XMLParser, all_points: Array[Vector2]) -> void:
	var junction_id := _attr(parser, "id")
	if junction_id.begins_with(":"):
		return
	if _attr(parser, "x").is_empty() or _attr(parser, "y").is_empty():
		return
	var point := Vector2(float(_attr(parser, "x")), float(_attr(parser, "y")))
	var junction = SumoJunctionGeometryScript.new()
	junction.configure(junction_id, point)
	if not junction.is_valid():
		return
	junctions.append(junction)
	all_points.append(point)


func _configure_bounds(points: Array[Vector2]) -> void:
	var min_value: Vector2 = points[0]
	var max_value: Vector2 = points[0]
	for point in points:
		min_value.x = min(min_value.x, point.x)
		min_value.y = min(min_value.y, point.y)
		max_value.x = max(max_value.x, point.x)
		max_value.y = max(max_value.y, point.y)
	bounds_min = min_value
	bounds_max = max_value
	has_bounds = true


func _parse_shape(shape: String) -> Array[Vector2]:
	var output: Array[Vector2] = []
	for token in shape.split(" ", false):
		var parts := token.split(",", false)
		if parts.size() < 2:
			continue
		output.append(Vector2(float(parts[0]), float(parts[1])))
	return output


func _attr(parser: XMLParser, name: String) -> String:
	for index in range(parser.get_attribute_count()):
		if parser.get_attribute_name(index) == name:
			return parser.get_attribute_value(index)
	return ""
