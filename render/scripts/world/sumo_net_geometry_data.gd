class_name SumoNetGeometryData
extends RefCounted

const SumoLaneGeometryScript := preload("res://scripts/world/sumo_lane_geometry.gd")
const SumoJunctionGeometryScript := preload("res://scripts/world/sumo_junction_geometry.gd")

var lanes: Array = []
var distance_lanes: Array = []
var junctions: Array = []
var lane_by_id: Dictionary = {}
var lane_to_edge: Dictionary = {}
var edge_to_lanes: Dictionary = {}
var bounds_min := Vector2.ZERO
var bounds_max := Vector2.ZERO
var has_bounds := false
var min_lane_width_m := 0.0
var max_lane_width_m := 0.0
var average_lane_width_m := 0.0
var errors: Array[String] = []


func load_xml(path: String) -> bool:
	lanes.clear()
	distance_lanes.clear()
	junctions.clear()
	lane_by_id.clear()
	lane_to_edge.clear()
	edge_to_lanes.clear()
	errors.clear()
	has_bounds = false
	bounds_min = Vector2.ZERO
	bounds_max = Vector2.ZERO
	min_lane_width_m = 0.0
	max_lane_width_m = 0.0
	average_lane_width_m = 0.0

	var parser := XMLParser.new()
	var open_error := parser.open(path)
	if open_error != OK:
		errors.append("SUMO net file not found for Godot world: %s" % path)
		return false

	var all_points: Array[Vector2] = []
	var current_edge_id := ""
	var current_edge_is_internal := false
	while parser.read() == OK:
		var node_type := parser.get_node_type()
		if node_type == XMLParser.NODE_ELEMENT_END and parser.get_node_name() == "edge":
			current_edge_id = ""
			current_edge_is_internal = false
			continue
		if node_type != XMLParser.NODE_ELEMENT:
			continue
		var node_name := parser.get_node_name()
		if node_name == "edge":
			current_edge_id = _attr(parser, "id")
			current_edge_is_internal = current_edge_id.begins_with(":") or _attr(parser, "function") == "internal"
			if not current_edge_is_internal and not current_edge_id.is_empty():
				edge_to_lanes[current_edge_id] = []
		elif node_name == "lane":
			_parse_lane(parser, current_edge_id, current_edge_is_internal, all_points)
		elif node_name == "junction":
			_parse_junction(parser, all_points)

	if all_points.is_empty():
		errors.append("SUMO net file has no lane or junction geometry: %s" % path)
		return false

	_configure_bounds(all_points)
	_configure_lane_width_stats()
	return errors.is_empty()


func lane_count() -> int:
	return lanes.size()


func junction_count() -> int:
	return junctions.size()


func distance_to_nearest_lane_m(point: Vector2) -> float:
	var search_lanes := distance_lanes if not distance_lanes.is_empty() else lanes
	if search_lanes.is_empty():
		return 0.0
	var best := INF
	for lane in search_lanes:
		best = min(best, float(lane.distance_to_point_m(point)))
	return best


func center_for_edge(edge_id: String) -> Variant:
	if not edge_to_lanes.has(edge_id):
		return null
	var lane_ids := edge_to_lanes[edge_id] as Array
	var points: Array[Vector2] = []
	for lane_id in lane_ids:
		if lane_by_id.has(lane_id):
			var lane = lane_by_id[lane_id]
			for point in lane.points:
				points.append(point as Vector2)
	if points.is_empty():
		return null
	var total := Vector2.ZERO
	for point in points:
		total += point
	return total / float(points.size())


func lane_width_summary() -> Dictionary:
	return {
		"min_lane_width_m": min_lane_width_m,
		"max_lane_width_m": max_lane_width_m,
		"average_lane_width_m": average_lane_width_m,
	}


func _parse_lane(
	parser: XMLParser,
	current_edge_id: String,
	current_edge_is_internal: bool,
	all_points: Array[Vector2]
) -> void:
	if current_edge_id.is_empty():
		return
	var shape := _attr(parser, "shape")
	var lane_id := _attr(parser, "id")
	if shape.is_empty():
		return
	var points := _parse_shape(shape)
	if points.size() < 2:
		return
	var lane = SumoLaneGeometryScript.new()
	var width := float(_attr(parser, "width")) if not _attr(parser, "width").is_empty() else 3.2
	lane.configure(lane_id, current_edge_id, points, width)
	if not lane.is_valid():
		return
	lane_by_id[lane_id] = lane
	distance_lanes.append(lane)
	for point in points:
		all_points.append(point)
	if current_edge_is_internal:
		return
	lanes.append(lane)
	lane_to_edge[lane_id] = current_edge_id
	if not edge_to_lanes.has(current_edge_id):
		edge_to_lanes[current_edge_id] = []
	(edge_to_lanes[current_edge_id] as Array).append(lane_id)


func _parse_junction(parser: XMLParser, all_points: Array[Vector2]) -> void:
	var junction_id := _attr(parser, "id")
	if junction_id.begins_with(":"):
		return
	if _attr(parser, "x").is_empty() or _attr(parser, "y").is_empty():
		return
	var point := Vector2(float(_attr(parser, "x")), float(_attr(parser, "y")))
	var shape := _parse_shape(_attr(parser, "shape"))
	var junction = SumoJunctionGeometryScript.new()
	junction.configure(junction_id, point, shape)
	if not junction.is_valid():
		return
	junctions.append(junction)
	all_points.append(point)
	for shape_point in shape:
		all_points.append(shape_point)


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


func _configure_lane_width_stats() -> void:
	var source_lanes := distance_lanes if not distance_lanes.is_empty() else lanes
	if source_lanes.is_empty():
		min_lane_width_m = 0.0
		max_lane_width_m = 0.0
		average_lane_width_m = 0.0
		return
	var min_width := INF
	var max_width := 0.0
	var total := 0.0
	for lane in source_lanes:
		var width := float(lane.width_m)
		min_width = min(min_width, width)
		max_width = max(max_width, width)
		total += width
	min_lane_width_m = min_width
	max_lane_width_m = max_width
	average_lane_width_m = total / float(source_lanes.size())


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
