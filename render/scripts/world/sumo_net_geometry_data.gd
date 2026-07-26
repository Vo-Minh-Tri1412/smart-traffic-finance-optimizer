class_name SumoNetGeometryData
extends RefCounted

const SumoLaneGeometryScript := preload("res://scripts/world/sumo_lane_geometry.gd")
const SumoJunctionGeometryScript := preload("res://scripts/world/sumo_junction_geometry.gd")
const ROAD_CLEARANCE_CELL_SIZE_M := 96.0

var lanes: Array = []
var distance_lanes: Array = []
var junctions: Array = []
var lane_by_id: Dictionary = {}
var road_clearance_lane_buckets: Dictionary = {}
var lane_to_edge: Dictionary = {}
var edge_to_lanes: Dictionary = {}
var edge_metadata_by_id: Dictionary = {}
var bounds_min := Vector2.ZERO
var bounds_max := Vector2.ZERO
var has_bounds := false
var min_lane_width_m := 0.0
var max_lane_width_m := 0.0
var average_lane_width_m := 0.0
var geo_boundary_min := Vector2.ZERO
var geo_boundary_max := Vector2.ZERO
var conv_boundary_min := Vector2.ZERO
var conv_boundary_max := Vector2.ZERO
var has_geo_transform := false
var errors: Array[String] = []


func load_xml(path: String) -> bool:
	lanes.clear()
	distance_lanes.clear()
	junctions.clear()
	lane_by_id.clear()
	road_clearance_lane_buckets.clear()
	lane_to_edge.clear()
	edge_to_lanes.clear()
	edge_metadata_by_id.clear()
	errors.clear()
	has_bounds = false
	bounds_min = Vector2.ZERO
	bounds_max = Vector2.ZERO
	min_lane_width_m = 0.0
	max_lane_width_m = 0.0
	average_lane_width_m = 0.0
	geo_boundary_min = Vector2.ZERO
	geo_boundary_max = Vector2.ZERO
	conv_boundary_min = Vector2.ZERO
	conv_boundary_max = Vector2.ZERO
	has_geo_transform = false

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
				edge_metadata_by_id[current_edge_id] = {
					"id": current_edge_id,
					"from": _attr(parser, "from"),
					"to": _attr(parser, "to"),
					"priority": int(_attr(parser, "priority")) if not _attr(parser, "priority").is_empty() else 0,
					"type": _attr(parser, "type"),
					"function": _attr(parser, "function"),
				}
		elif node_name == "lane":
			_parse_lane(parser, current_edge_id, current_edge_is_internal, all_points)
		elif node_name == "junction":
			_parse_junction(parser, all_points)
		elif node_name == "location":
			_parse_location(parser)

	if all_points.is_empty():
		errors.append("SUMO net file has no lane or junction geometry: %s" % path)
		return false

	_configure_bounds(all_points)
	_configure_lane_width_stats()
	_configure_road_clearance_index()
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


func is_point_clear_of_roads_m(point: Vector2, required_clearance_m: float) -> bool:
	var clearance: float = max(0.0, required_clearance_m)
	if clearance <= 0.0001 or road_clearance_lane_buckets.is_empty():
		return true
	var min_cell := _road_clearance_cell_for(point - Vector2.ONE * clearance)
	var max_cell := _road_clearance_cell_for(point + Vector2.ONE * clearance)
	var seen_lane_ids: Dictionary = {}
	for cell_x in range(int(min_cell.x), int(max_cell.x) + 1):
		for cell_y in range(int(min_cell.y), int(max_cell.y) + 1):
			var bucket_key := _road_clearance_bucket_key(cell_x, cell_y)
			var raw_bucket: Variant = road_clearance_lane_buckets.get(bucket_key, [])
			if not (raw_bucket is Array):
				continue
			for lane in raw_bucket as Array:
				if lane == null:
					continue
				var lane_id := String(lane.lane_id)
				if seen_lane_ids.has(lane_id):
					continue
				seen_lane_ids[lane_id] = true
				if float(lane.distance_to_point_m(point)) < clearance:
					return false
	return true


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


func metadata_for_edge(edge_id: String) -> Dictionary:
	if edge_metadata_by_id.has(edge_id):
		return edge_metadata_by_id[edge_id] as Dictionary
	return {}


func sumo_point_for_lon_lat(lon: float, lat: float) -> Variant:
	if not has_geo_transform:
		return null
	var lon_span := geo_boundary_max.x - geo_boundary_min.x
	var lat_span := geo_boundary_max.y - geo_boundary_min.y
	if abs(lon_span) <= 0.0000001 or abs(lat_span) <= 0.0000001:
		return null
	var x_ratio := (lon - geo_boundary_min.x) / lon_span
	var y_ratio := (lat - geo_boundary_min.y) / lat_span
	return Vector2(
		lerp(conv_boundary_min.x, conv_boundary_max.x, x_ratio),
		lerp(conv_boundary_min.y, conv_boundary_max.y, y_ratio)
	)


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
	var speed := float(_attr(parser, "speed")) if not _attr(parser, "speed").is_empty() else 0.0
	var length := float(_attr(parser, "length")) if not _attr(parser, "length").is_empty() else 0.0
	lane.configure(
		lane_id,
		current_edge_id,
		points,
		width,
		speed,
		length,
		_attr(parser, "allow"),
		_attr(parser, "disallow")
	)
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
	var junction_type := _attr(parser, "type")
	var junction = SumoJunctionGeometryScript.new()
	junction.configure(junction_id, point, shape, junction_type)
	if not junction.is_valid():
		return
	junctions.append(junction)
	all_points.append(point)
	for shape_point in shape:
		all_points.append(shape_point)


func _parse_location(parser: XMLParser) -> void:
	var orig_boundary := _parse_boundary(_attr(parser, "origBoundary"))
	var conv_boundary := _parse_boundary(_attr(parser, "convBoundary"))
	if orig_boundary.size() != 4 or conv_boundary.size() != 4:
		return
	geo_boundary_min = Vector2(float(orig_boundary[0]), float(orig_boundary[1]))
	geo_boundary_max = Vector2(float(orig_boundary[2]), float(orig_boundary[3]))
	conv_boundary_min = Vector2(float(conv_boundary[0]), float(conv_boundary[1]))
	conv_boundary_max = Vector2(float(conv_boundary[2]), float(conv_boundary[3]))
	has_geo_transform = true


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


func _configure_road_clearance_index() -> void:
	road_clearance_lane_buckets.clear()
	for lane in distance_lanes:
		if lane == null or not (lane.points is Array) or (lane.points as Array).size() < 2:
			continue
		var minimum := lane.points[0] as Vector2
		var maximum := minimum
		for raw_point in lane.points:
			var point := raw_point as Vector2
			minimum.x = min(minimum.x, point.x)
			minimum.y = min(minimum.y, point.y)
			maximum.x = max(maximum.x, point.x)
			maximum.y = max(maximum.y, point.y)
		var min_cell := _road_clearance_cell_for(minimum)
		var max_cell := _road_clearance_cell_for(maximum)
		for cell_x in range(int(min_cell.x), int(max_cell.x) + 1):
			for cell_y in range(int(min_cell.y), int(max_cell.y) + 1):
				var bucket_key := _road_clearance_bucket_key(cell_x, cell_y)
				if not road_clearance_lane_buckets.has(bucket_key):
					road_clearance_lane_buckets[bucket_key] = []
				(road_clearance_lane_buckets[bucket_key] as Array).append(lane)


func _road_clearance_cell_for(point: Vector2) -> Vector2i:
	return Vector2i(
		floori(point.x / ROAD_CLEARANCE_CELL_SIZE_M),
		floori(point.y / ROAD_CLEARANCE_CELL_SIZE_M)
	)


func _road_clearance_bucket_key(cell_x: int, cell_y: int) -> String:
	return "%d:%d" % [cell_x, cell_y]


func _parse_shape(shape: String) -> Array[Vector2]:
	var output: Array[Vector2] = []
	for token in shape.split(" ", false):
		var parts := token.split(",", false)
		if parts.size() < 2:
			continue
		output.append(Vector2(float(parts[0]), float(parts[1])))
	return output


func _parse_boundary(value: String) -> Array:
	var parts := value.split(",", false)
	if parts.size() != 4:
		return []
	return [float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])]


func _attr(parser: XMLParser, name: String) -> String:
	for index in range(parser.get_attribute_count()):
		if parser.get_attribute_name(index) == name:
			return parser.get_attribute_value(index)
	return ""
