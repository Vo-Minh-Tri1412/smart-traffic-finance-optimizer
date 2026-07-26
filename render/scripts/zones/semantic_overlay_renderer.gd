@tool
class_name SemanticOverlayRenderer
extends Node3D

const ZoneVisualFactoryScript := preload("res://scripts/assets/zone_visual_factory.gd")

@export var overlay_path := ""
@export var zone_catalog_path := "res://resources/catalogs/ZoneAssetCatalog.tres"
@export var geometry_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var auto_render := true
@export var editor_preview_enabled := false
@export var show_zone_labels := false
@export var render_neutral_zones := true
@export_group("Camera Zone Streaming")
@export var use_camera_zone_lod := true
@export_node_path("Node3D") var zone_lod_target_path: NodePath = NodePath("../Camera3D")
@export var zone_lod_radius_m := 720.0
@export var zone_lod_prefetch_distance_m := 520.0
@export var zone_lod_exit_margin_m := 180.0
@export var zone_lod_rebuild_distance_m := 70.0
@export var zone_lod_update_interval_seconds := 0.20
@export var rebuild_editor_preview := false:
	set(value):
		rebuild_editor_preview = false
		if value and Engine.is_editor_hint() and editor_preview_enabled:
			call_deferred("_auto_render")
@export var fallback_ring_radius := 8.0

var zone_factory = null
var spawned_zone_count := 0
var fallback_zone_count := 0
var overlay_parse_error_count := 0
var skipped_neutral_count := 0
var skipped_zone_count := 0
var skipped_zone_lod_count := 0
var spawned_neutral_zone_count := 0
var candidate_zone_count := 0
var streamed_in_zone_count := 0
var streamed_out_zone_count := 0
var errors: Array[String] = []

var _loaded_overlay_data: Dictionary = {}
var _zone_records: Dictionary = {}
var _active_zone_nodes: Dictionary = {}
var _zone_lod_timer := 0.0
var _has_lod_focus := false
var _last_lod_focus_world := Vector3.ZERO
var _last_lod_forward_world := Vector3.FORWARD
var _rebuild_count := 0

func _ready() -> void:
	if Engine.is_editor_hint():
		if editor_preview_enabled and auto_render:
			call_deferred("_auto_render")
		return
	set_process(use_camera_zone_lod)
	if auto_render:
		call_deferred("_auto_render")

func _process(delta: float) -> void:
	if Engine.is_editor_hint() or not use_camera_zone_lod:
		return
	if overlay_path.is_empty() or _loaded_overlay_data.is_empty():
		return
	_zone_lod_timer += delta
	if _zone_lod_timer < zone_lod_update_interval_seconds:
		return
	_zone_lod_timer = 0.0
	var focus_world: Variant = _zone_lod_focus_world()
	if focus_world is Vector3:
		var current_focus := focus_world as Vector3
		var current_forward := _zone_lod_forward_world()
		var moved := current_focus.distance_to(_last_lod_focus_world) >= zone_lod_rebuild_distance_m
		var turned := current_forward.dot(_last_lod_forward_world) < 0.96
		if not _has_lod_focus or moved or turned:
			_rebuild_lod_region()


func _auto_render() -> void:
	if not overlay_path.is_empty():
		render_overlay(overlay_path)


func render_overlay(path: String) -> bool:
	errors.clear()
	overlay_parse_error_count = 0
	overlay_path = path
	var overlay := _load_overlay(path)
	_loaded_overlay_data = overlay
	_clear_generated()
	_reset_render_counts()
	_zone_records.clear()
	if overlay.is_empty():
		_has_lod_focus = false
		return false
	if not _configure_zone_factory():
		return false
	_prepare_zone_records()
	return _rebuild_lod_region()

func _rebuild_lod_region() -> bool:
	_rebuild_count += 1
	if _loaded_overlay_data.is_empty() or _zone_records.is_empty():
		return false
	var stream_state := _zone_stream_state()
	if use_camera_zone_lod and stream_state.is_empty():
		return false
	var desired_records: Dictionary = {}
	var sorted_desired: Array = []
	skipped_zone_lod_count = 0
	for raw_record in _zone_records.values():
		if not (raw_record is Dictionary):
			continue
		var record := raw_record as Dictionary
		var record_id := str(record.get("id", ""))
		var is_active := _active_zone_nodes.has(record_id)
		var stream_distance := _record_stream_distance(record, stream_state)
		if use_camera_zone_lod and not _record_is_in_stream(stream_distance, stream_state, is_active):
			skipped_zone_lod_count += 1
			continue
		var prioritized := record.duplicate()
		prioritized["stream_distance"] = stream_distance
		desired_records[record_id] = prioritized
		sorted_desired.append(prioritized)
	candidate_zone_count = desired_records.size()
	sorted_desired.sort_custom(
		func(left, right): return float((left as Dictionary).get("stream_distance", 0.0)) < float((right as Dictionary).get("stream_distance", 0.0))
	)
	for active_id in _active_zone_nodes.keys():
		if desired_records.has(active_id):
			continue
		var zone_node := _active_zone_nodes.get(active_id) as Node
		if zone_node != null:
			remove_child(zone_node)
			zone_node.queue_free()
		_active_zone_nodes.erase(active_id)
		streamed_out_zone_count += 1
	var world := get_node_or_null(geometry_world_path)
	for raw_record in sorted_desired:
		var record := raw_record as Dictionary
		var record_id := str(record.get("id", ""))
		if _active_zone_nodes.has(record_id):
			continue
		if not _spawn_zone_record(record, world):
			overlay_parse_error_count += 1
			continue
		streamed_in_zone_count += 1
	_update_active_zone_counts()
	var focus_world: Variant = _zone_lod_focus_world()
	if focus_world is Vector3:
		_last_lod_focus_world = focus_world as Vector3
		_last_lod_forward_world = _zone_lod_forward_world()
		_has_lod_focus = true
	if zone_factory != null:
		fallback_zone_count = zone_factory.fallback_spawn_count
	return spawned_zone_count > 0 and overlay_parse_error_count == 0


func _reset_render_counts() -> void:
	spawned_zone_count = 0
	fallback_zone_count = 0
	skipped_neutral_count = 0
	skipped_zone_count = 0
	skipped_zone_lod_count = 0
	spawned_neutral_zone_count = 0
	candidate_zone_count = 0
	streamed_in_zone_count = 0
	streamed_out_zone_count = 0


func _configure_zone_factory() -> bool:
	if zone_factory == null:
		zone_factory = ZoneVisualFactoryScript.new()
		if not zone_factory.configure(zone_catalog_path):
			for error in zone_factory.errors:
				push_warning(error)
			return false
	return true


func _prepare_zone_records() -> void:
	var raw_zones: Variant = _loaded_overlay_data.get("zones", [])
	if not (raw_zones is Array):
		errors.append("Semantic overlay zones must be an array: %s" % overlay_path)
		return
	var world := get_node_or_null(geometry_world_path)
	var zones := raw_zones as Array
	for index in range(zones.size()):
		var raw_zone = zones[index]
		if not (raw_zone is Dictionary):
			overlay_parse_error_count += 1
			continue
		var zone_data := raw_zone as Dictionary
		var zone_type := str(zone_data.get("type", zone_data.get("zone_type", ""))).strip_edges().to_lower()
		if zone_type == "neutral" and not render_neutral_zones:
			skipped_neutral_count += 1
			continue
		var world_polygons := _zone_world_polygons(zone_data, world)
		if world_polygons.is_empty():
			_register_zone_record(
				zone_data,
				[],
				_zone_world_position(zone_data, world, index, zones.size()),
				zone_type
			)
			continue
		var part_index := 0
		for raw_polygon in world_polygons:
			if not (raw_polygon is Array):
				continue
			var world_polygon := raw_polygon as Array
			if world_polygon.size() < 3:
				continue
			var part_data := zone_data.duplicate(true)
			part_data["id"] = "%s_part_%d" % [str(zone_data.get("id", "zone")), part_index + 1]
			_register_zone_record(part_data, world_polygon, _polygon_centroid(world_polygon), zone_type)
			part_index += 1


func _register_zone_record(
	zone_data: Dictionary,
	world_polygon: Array,
	zone_position: Vector3,
	zone_type: String
) -> void:
	var record_id := str(zone_data.get("id", "")).strip_edges()
	if record_id.is_empty():
		overlay_parse_error_count += 1
		return
	if zone_type == "neutral":
		zone_position.y = 0.004
	else:
		zone_position.y = 0.012
	_zone_records[record_id] = {
		"id": record_id,
		"zone_data": zone_data,
		"world_polygon": world_polygon,
		"position": zone_position,
		"type": zone_type,
		"radius_world": _polygon_radius_world(world_polygon, zone_position),
	}


func _spawn_zone_record(record: Dictionary, world: Node) -> bool:
	var zone_data := record.get("zone_data", {}) as Dictionary
	var world_polygon := record.get("world_polygon", []) as Array
	var zone_node: Node3D = zone_factory.create_zone(zone_data)
	if zone_node == null:
		return false
	var zone_position := record.get("position", Vector3.ZERO) as Vector3
	zone_node.position = zone_position
	zone_node.set("show_label", show_zone_labels)
	if world != null and zone_node.has_method("configure_road_clearance_world"):
		zone_node.configure_road_clearance_world(world)
	if (
		world != null
		and zone_node.has_method("configure_world_units_per_meter")
		and world.get("world_scale") != null
	):
		zone_node.configure_world_units_per_meter(float(world.get("world_scale")))
	if not world_polygon.is_empty() and zone_node.has_method("configure_zone_polygon"):
		zone_node.configure_zone_polygon(_local_polygon(world_polygon, zone_position))
	zone_node.add_to_group("generated_zone_visual")
	add_child(zone_node)
	_active_zone_nodes[str(record.get("id", ""))] = zone_node
	return true


func summary() -> Dictionary:
	return {
		"spawned_zone_count": spawned_zone_count,
		"fallback_zone_count": fallback_zone_count,
		"overlay_parse_error_count": overlay_parse_error_count,
		"skipped_neutral_count": skipped_neutral_count,
		"skipped_zone_count": skipped_zone_count,
		"skipped_zone_lod_count": skipped_zone_lod_count,
		"spawned_neutral_zone_count": spawned_neutral_zone_count,
		"candidate_zone_count": candidate_zone_count,
		"streamed_in_zone_count": streamed_in_zone_count,
		"streamed_out_zone_count": streamed_out_zone_count,
		"streaming_model": "camera_corridor_incremental",
		"rebuild_count": _rebuild_count,
		"has_lod_focus": _has_lod_focus,
		"last_lod_focus_world": {
			"x": float(_last_lod_focus_world.x) if is_finite(_last_lod_focus_world.x) else 0.0,
			"y": float(_last_lod_focus_world.y) if is_finite(_last_lod_focus_world.y) else 0.0,
			"z": float(_last_lod_focus_world.z) if is_finite(_last_lod_focus_world.z) else 0.0,
		},
		"overlay_path": overlay_path,
		"zone_catalog_path": zone_catalog_path,
		"zone_asset_catalog_loaded": (
			zone_factory.catalog_loaded() if zone_factory != null else false
		),
		"registered_zone_type_count": (
			zone_factory.registered_zone_type_count() if zone_factory != null else 0
		),
	}


func _load_overlay(path: String) -> Dictionary:
	var resolved_path := _resolve_repo_path(path)
	var file := FileAccess.open(resolved_path, FileAccess.READ)
	if file == null:
		errors.append("Semantic overlay not found: %s" % path)
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		errors.append("Semantic overlay must be a JSON object: %s" % path)
		overlay_parse_error_count += 1
		return {}
	return parsed as Dictionary


func _resolve_repo_path(path: String) -> String:
	if not path.begins_with("repo://"):
		return path
	var relative_path := path.trim_prefix("repo://").trim_prefix("/")
	var render_project_path := ProjectSettings.globalize_path("res://").trim_suffix("/")
	return render_project_path.get_base_dir().path_join(relative_path)


func _zone_world_position(zone_data: Dictionary, world: Node, index: int, total: int) -> Vector3:
	if world != null and world.has_method("world_position_for_edge_ids"):
		var anchor_edges = zone_data.get("anchor_edges", [])
		var anchor_position = world.world_position_for_edge_ids(anchor_edges)
		if anchor_position is Vector3:
			return (anchor_position as Vector3) + Vector3(0.0, 0.15, 0.0)
	var angle := TAU * float(index) / float(max(1, total))
	return Vector3(cos(angle) * fallback_ring_radius, 0.15, sin(angle) * fallback_ring_radius)


func _zone_stream_state() -> Dictionary:
	if not use_camera_zone_lod:
		return {"radius_world": INF, "exit_margin_world": 0.0}
	var focus_world: Variant = _zone_lod_focus_world()
	if not (focus_world is Vector3):
		return {}
	var world_scale := 1.0
	var world := get_node_or_null(geometry_world_path)
	if world != null and world.get("world_scale") != null:
		world_scale = max(0.0001, float(world.get("world_scale")))
	var focus := focus_world as Vector3
	var forward := _zone_lod_forward_world()
	var prefetch_world: float = max(0.0, zone_lod_prefetch_distance_m) * world_scale
	return {
		"focus": focus,
		"prefetch_end": focus + forward * prefetch_world,
		"radius_world": max(1.0, zone_lod_radius_m * world_scale),
		"exit_margin_world": max(0.0, zone_lod_exit_margin_m * world_scale),
	}


func _record_is_in_stream(
	stream_distance: float,
	stream_state: Dictionary,
	is_active: bool
) -> bool:
	if not use_camera_zone_lod:
		return true
	if stream_state.is_empty():
		return false
	var radius := float(stream_state.get("radius_world", 0.0))
	if is_active:
		radius += float(stream_state.get("exit_margin_world", 0.0))
	return stream_distance <= radius


func _record_stream_distance(record: Dictionary, stream_state: Dictionary) -> float:
	if not use_camera_zone_lod:
		return 0.0
	if stream_state.is_empty():
		return INF
	var position := record.get("position", Vector3.ZERO) as Vector3
	var point := Vector2(position.x, position.z)
	var focus := stream_state.get("focus", Vector3.ZERO) as Vector3
	var prefetch_end := stream_state.get("prefetch_end", focus) as Vector3
	var capsule_distance := _distance_to_segment_2d(
		point,
		Vector2(focus.x, focus.z),
		Vector2(prefetch_end.x, prefetch_end.z)
	)
	return max(0.0, capsule_distance - float(record.get("radius_world", 0.0)))


func _distance_to_segment_2d(point: Vector2, start: Vector2, end: Vector2) -> float:
	var segment := end - start
	var length_squared := segment.length_squared()
	if length_squared <= 0.000001:
		return point.distance_to(start)
	var progress: float = clamp((point - start).dot(segment) / length_squared, 0.0, 1.0)
	return point.distance_to(start + segment * progress)


func _polygon_radius_world(world_polygon: Array, position: Vector3) -> float:
	var radius := 0.0
	for raw_point in world_polygon:
		if not (raw_point is Vector3):
			continue
		var point := raw_point as Vector3
		radius = max(radius, Vector2(point.x, point.z).distance_to(Vector2(position.x, position.z)))
	return radius


func _update_active_zone_counts() -> void:
	spawned_zone_count = _active_zone_nodes.size()
	spawned_neutral_zone_count = 0
	for record_id in _active_zone_nodes.keys():
		var record := _zone_records.get(record_id, {}) as Dictionary
		if str(record.get("type", "")) == "neutral":
			spawned_neutral_zone_count += 1


func _zone_lod_forward_world() -> Vector3:
	var target := get_node_or_null(zone_lod_target_path)
	if target is Node3D:
		var forward := -(target as Node3D).global_transform.basis.z
		forward.y = 0.0
		if forward.length_squared() > 0.000001:
			return forward.normalized()
	return Vector3.FORWARD


func _zone_lod_focus_world() -> Variant:
	var target := get_node_or_null(zone_lod_target_path)
	if target is Node3D:
		return (target as Node3D).global_position
	return null


func _zone_world_polygons(zone_data: Dictionary, world: Node) -> Array:
	if world == null or not world.has_method("world_polygon_for_geo_coordinates"):
		return []
	var geometry = zone_data.get("geometry", {})
	if not (geometry is Dictionary):
		return []
	var geometry_data := geometry as Dictionary
	var geometry_type := str(geometry_data.get("type", "")).to_lower()
	var coordinate_system := str(
		geometry_data.get("coordinate_system", zone_data.get("coordinate_system", "lon_lat"))
	).to_lower()
	if geometry_type == "polygon":
		var polygon := _world_polygon_for_coordinates(
			geometry_data.get("coordinates", []),
			world,
			coordinate_system
		)
		if polygon.size() >= 3:
			return [polygon]
		return []
	if geometry_type == "multipolygon":
		var output := []
		var polygon_parts = geometry_data.get("coordinates", [])
		if not (polygon_parts is Array):
			return output
		for raw_part in polygon_parts as Array:
			var part_coordinates = _first_polygon_ring(raw_part)
			var polygon := _world_polygon_for_coordinates(part_coordinates, world, coordinate_system)
			if polygon.size() >= 3:
				output.append(polygon)
		return output
	return []


func _world_polygon_for_coordinates(coordinates, world: Node, coordinate_system: String) -> Array:
	var normalized := coordinate_system.strip_edges().to_lower()
	if normalized in ["sumo_xy", "sumo", "sumo_meters"]:
		if world.has_method("world_polygon_for_sumo_coordinates"):
			var world_polygon = world.world_polygon_for_sumo_coordinates(coordinates, 0.04)
			if world_polygon is Array:
				return world_polygon as Array
		return []
	var geo_polygon = world.world_polygon_for_geo_coordinates(coordinates, 0.04)
	if geo_polygon is Array:
		return geo_polygon as Array
	return []


func _first_polygon_ring(raw_part) -> Array:
	if not (raw_part is Array):
		return []
	var part := raw_part as Array
	if part.is_empty():
		return []
	if part[0] is Array:
		var first := part[0] as Array
		if not first.is_empty() and first[0] is Array:
			return first
	return part


func _polygon_centroid(points: Array) -> Vector3:
	if points.is_empty():
		return Vector3.ZERO
	var total := Vector3.ZERO
	var count := 0
	for point in points:
		if point is Vector3:
			total += point as Vector3
			count += 1
	if count == 0:
		return Vector3.ZERO
	var center := total / float(count)
	center.y = 0.04
	return center


func _local_polygon(points: Array, origin: Vector3) -> Array:
	var output: Array[Vector3] = []
	for point in points:
		if not (point is Vector3):
			continue
		var value := point as Vector3
		output.append(Vector3(value.x - origin.x, 0.0, value.z - origin.z))
	return output


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("generated_zone_visual"):
			remove_child(child)
			child.queue_free()
	_active_zone_nodes.clear()
