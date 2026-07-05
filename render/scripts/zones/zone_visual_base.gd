@tool
class_name ZoneVisualBase
extends Node3D

@onready var ground: MeshInstance3D = $ZoneGround
@onready var label: Label3D = $ZoneLabel
@onready var building_cluster_root: Node3D = $BuildingClusterRoot

@export var default_zone_type := "mixed"
@export var default_zone_color := Color(0.2, 0.7, 0.35, 0.32)
@export var default_ground_size := Vector3(5.0, 0.08, 5.0)
@export var building_spacing := 1.45
@export var world_units_per_meter := 0.02:
	set(value):
		world_units_per_meter = max(0.0001, value)
		_request_zone_refresh()

@export_group("Scene Zone Assets")
@export var preview_catalog_path := "res://resources/catalogs/ZoneAssetCatalog.tres":
	set(value):
		preview_catalog_path = value
		_request_zone_refresh()
@export var ground_material: Material:
	set(value):
		ground_material = value
		_request_zone_refresh()
@export var building_scenes: Array[PackedScene] = []:
	set(value):
		building_scenes = value
		_request_zone_refresh()
@export var building_scene_paths: PackedStringArray = PackedStringArray():
	set(value):
		building_scene_paths = value
		_request_zone_refresh()
@export var building_density := 3:
	set(value):
		building_density = max(0, value)
		_request_zone_refresh()
@export var min_building_scale := 0.8:
	set(value):
		min_building_scale = value
		_request_zone_refresh()
@export var max_building_scale := 1.25:
	set(value):
		max_building_scale = value
		_request_zone_refresh()
@export var building_asset_scale := 0.05:
	set(value):
		building_asset_scale = value
		_request_zone_refresh()
@export var building_asset_offset := Vector3.ZERO:
	set(value):
		building_asset_offset = value
		_request_zone_refresh()
@export var building_ground_clearance := 0.02:
	set(value):
		building_ground_clearance = value
		_request_zone_refresh()
@export var building_override_material: Material:
	set(value):
		building_override_material = value
		_request_zone_refresh()
@export var placement_profile: Resource:
	set(value):
		placement_profile = value
		_request_zone_refresh()
@export var seed := 17:
	set(value):
		seed = value
		_request_zone_refresh()
@export var label_prefix := "":
	set(value):
		label_prefix = value
		_request_zone_refresh()
@export var show_label := false:
	set(value):
		show_label = value
		_request_zone_refresh()
@export var show_editor_building_preview := true:
	set(value):
		show_editor_building_preview = value
		_request_zone_refresh()
@export var rebuild_zone_preview := false:
	set(value):
		rebuild_zone_preview = false
		_request_zone_refresh()

var zone_id := ""
var zone_type := ""
var display_name := ""
var _configured_zone_entry = null
var _configured_ground_polygon: Array[Vector3] = []


func configure_zone(zone_data: Dictionary, zone_entry = null) -> void:
	zone_id = str(zone_data.get("id", ""))
	zone_type = str(zone_data.get("type", zone_data.get("zone_type", default_zone_type)))
	display_name = str(zone_data.get("name", zone_data.get("display_name", zone_id)))
	name = _safe_node_name("Zone_%s" % (zone_id if not zone_id.is_empty() else zone_type))
	_configured_zone_entry = zone_entry
	if is_node_ready():
		_refresh_zone_visuals()


func configure_zone_polygon(local_polygon: Array) -> void:
	_configured_ground_polygon.clear()
	for point in local_polygon:
		if point is Vector3:
			_configured_ground_polygon.append(point as Vector3)
	if is_node_ready():
		_refresh_zone_visuals()


func configure_world_units_per_meter(value: float) -> void:
	world_units_per_meter = max(0.0001, value)
	if is_node_ready():
		_refresh_zone_visuals()


func _ready() -> void:
	if zone_type.is_empty():
		zone_type = default_zone_type
	_refresh_zone_visuals()


func _refresh_zone_visuals() -> void:
	var zone_entry = _effective_zone_entry()
	_apply_label(zone_entry)
	_apply_ground(zone_entry)
	_build_building_cluster(zone_entry)


func _apply_label(zone_entry) -> void:
	var label_node := _label_node()
	if label_node == null:
		return
	label_node.visible = show_label
	var prefix := label_prefix
	if prefix.is_empty() and zone_entry != null:
		prefix = str(zone_entry.get("label_prefix"))
	label_node.text = "%s%s" % [prefix, display_name if not display_name.is_empty() else zone_type]


func _apply_ground(zone_entry) -> void:
	var ground_node := _ground_node()
	if ground_node == null:
		return
	if _configured_ground_polygon.size() >= 3:
		var polygon_mesh := _ground_polygon_mesh(_configured_ground_polygon)
		if polygon_mesh != null:
			ground_node.mesh = polygon_mesh
	else:
		var mesh := ground_node.mesh
		if mesh is BoxMesh:
			(mesh as BoxMesh).size = default_ground_size
	var material = ground_material
	if material == null and zone_entry != null:
		material = zone_entry.get("ground_material")
	if material is Material:
		ground_node.set_surface_override_material(0, material)
	else:
		var fallback := StandardMaterial3D.new()
		fallback.albedo_color = default_zone_color
		fallback.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		ground_node.set_surface_override_material(0, fallback)


func _ground_polygon_mesh(local_polygon: Array[Vector3]) -> ArrayMesh:
	if local_polygon.size() < 3:
		return null
	var polygon_2d := PackedVector2Array()
	for point in local_polygon:
		polygon_2d.append(Vector2(point.x, point.z))
	var triangulated := Geometry2D.triangulate_polygon(polygon_2d)
	if triangulated.size() < 3:
		return null
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	for point in local_polygon:
		vertices.append(Vector3(point.x, 0.0, point.z))
		normals.append(Vector3.UP)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = triangulated
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


func _build_building_cluster(zone_entry) -> void:
	var cluster_root := _building_cluster_root_node()
	if cluster_root == null:
		return
	for child in cluster_root.get_children():
		cluster_root.remove_child(child)
		child.queue_free()
	if Engine.is_editor_hint() and not show_editor_building_preview:
		return

	var config := _resolve_building_config(zone_entry)
	var active_profile = config.get("profile")
	var active_building_scenes: Array = config.get("building_scenes", [])
	var active_seed: int = int(config.get("seed", seed + zone_id.length() * 97))
	var active_building_asset_scale: float = float(config.get("asset_scale", building_asset_scale))
	var active_building_asset_offset: Vector3 = config.get("asset_offset", building_asset_offset)
	var active_building_ground_clearance: float = float(
		config.get("ground_clearance", building_ground_clearance)
	)
	var active_building_override_material: Material = config.get("override_material")
	var min_scale: float = float(config.get("min_scale", min_building_scale))
	var max_scale: float = float(config.get("max_scale", max_building_scale))

	var rng := RandomNumberGenerator.new()
	rng.seed = active_seed
	var ground_polygon := _active_ground_polygon_2d()
	var desired_count := _desired_building_count(active_profile, int(config.get("density", 0)), ground_polygon)
	if desired_count <= 0:
		return
	var positions := _building_positions(active_profile, ground_polygon, desired_count, rng)
	if positions.is_empty():
		return

	var base_rotation_y := _dominant_polygon_rotation_y(ground_polygon)
	var count: int = min(desired_count, positions.size())
	for index in range(count):
		var target_footprint_m2 := _random_profile_footprint_m2(active_profile, rng)
		var floor_count := _random_profile_floor_count(active_profile, rng)
		var building: Node3D = _instantiate_building(
			active_building_scenes,
			index,
			active_building_asset_scale,
			active_building_asset_offset,
			active_building_ground_clearance,
			active_building_override_material,
			target_footprint_m2,
			floor_count,
			active_profile
		)
		if building == null:
			continue
		building.scale *= _asset_scale_multiplier(active_profile, target_footprint_m2, rng, building)
		building.rotation.y = _building_rotation_y(active_profile, base_rotation_y, rng, index)
		var position := positions[index] as Vector3
		building.position.x += position.x
		building.position.z += position.z
		_align_node_bottom_to_ground(building, active_building_ground_clearance)
		cluster_root.add_child(building)


func _resolve_building_config(zone_entry) -> Dictionary:
	var active_building_scenes: Array = []
	var density := building_density
	var min_scale := min_building_scale
	var max_scale := max_building_scale
	var active_building_asset_scale := building_asset_scale
	var active_building_asset_offset := building_asset_offset
	var active_building_ground_clearance := building_ground_clearance
	var active_building_override_material: Material = building_override_material
	var active_seed := seed + zone_id.length() * 97
	var active_profile: Resource = placement_profile
	var scene_has_building_assets := not building_scenes.is_empty() or not building_scene_paths.is_empty()
	if zone_entry != null:
		var raw_building_scenes = zone_entry.get("building_scenes")
		if raw_building_scenes is Array:
			active_building_scenes = raw_building_scenes as Array
		var raw_building_scene_paths = zone_entry.get("building_scene_paths")
		if raw_building_scene_paths is PackedStringArray:
			for scene_path in raw_building_scene_paths:
				var loaded_scene: Resource = load(str(scene_path))
				if loaded_scene is PackedScene:
					active_building_scenes.append(loaded_scene)
		density = max(0, int(zone_entry.get("building_density")))
		min_scale = float(zone_entry.get("min_building_scale"))
		max_scale = float(zone_entry.get("max_building_scale"))
		active_building_asset_scale = float(zone_entry.get("building_asset_scale"))
		if zone_entry.get("building_asset_offset") is Vector3:
			active_building_asset_offset = zone_entry.get("building_asset_offset") as Vector3
		active_building_ground_clearance = float(zone_entry.get("building_ground_clearance"))
		var raw_material = zone_entry.get("building_override_material")
		if raw_material is Material:
			active_building_override_material = raw_material
		var raw_profile = zone_entry.get("placement_profile")
		if raw_profile is Resource:
			active_profile = raw_profile as Resource
		active_seed += int(zone_entry.get("seed"))
	if building_override_material != null:
		active_building_override_material = building_override_material
	if placement_profile != null:
		active_profile = placement_profile
	if scene_has_building_assets:
		active_building_scenes.clear()
		active_building_scenes.append_array(building_scenes)
		for scene_path in building_scene_paths:
			var loaded_scene: Resource = load(str(scene_path))
			if loaded_scene is PackedScene:
				active_building_scenes.append(loaded_scene)
	return {
		"building_scenes": active_building_scenes,
		"density": density,
		"min_scale": min_scale,
		"max_scale": max_scale,
		"asset_scale": active_building_asset_scale,
		"asset_offset": active_building_asset_offset,
		"ground_clearance": active_building_ground_clearance,
		"override_material": active_building_override_material,
		"seed": active_seed,
		"profile": active_profile,
	}


func _instantiate_building(
	building_scenes: Array,
	index: int,
	building_asset_scale: float,
	building_asset_offset: Vector3,
	building_ground_clearance: float,
	building_override_material: Material,
	target_footprint_m2: float,
	floor_count: int,
	profile
) -> Node3D:
	if not building_scenes.is_empty():
		var raw_scene = building_scenes[index % building_scenes.size()]
		if raw_scene is PackedScene:
			var instance = (raw_scene as PackedScene).instantiate()
			if instance is Node3D:
				var wrapper := Node3D.new()
				wrapper.name = "BuildingAsset_%d" % index
				wrapper.scale = Vector3.ONE * max(0.001, building_asset_scale)
				wrapper.add_child(instance as Node3D)
				if building_override_material != null:
					_apply_material_recursive(wrapper, building_override_material)
				var local_min_y: float = _node_local_min_y(wrapper)
				wrapper.position = building_asset_offset
				wrapper.position.y += -local_min_y + building_ground_clearance
				return wrapper
			if instance != null:
				instance.queue_free()
	var placeholder := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	var side_world := sqrt(max(1.0, target_footprint_m2)) * world_units_per_meter
	var floor_height_m := 3.2
	if profile != null:
		floor_height_m = max(1.5, float(profile.get("floor_height_m")))
	var height_world: float = max(
		0.2,
		float(max(1, floor_count)) * floor_height_m * world_units_per_meter
	)
	mesh.size = Vector3(side_world, height_world, side_world)
	placeholder.mesh = mesh
	placeholder.position = Vector3(0.0, mesh.size.y / 2.0 + building_ground_clearance, 0.0) + building_asset_offset
	var material := StandardMaterial3D.new()
	material.albedo_color = default_zone_color.lightened(0.25)
	placeholder.set_surface_override_material(0, material)
	return placeholder


func _active_ground_polygon_2d() -> PackedVector2Array:
	var polygon := PackedVector2Array()
	if _configured_ground_polygon.size() >= 3:
		for point in _configured_ground_polygon:
			polygon.append(Vector2(point.x, point.z))
		return polygon
	var half_x: float = max(0.1, default_ground_size.x * 0.5)
	var half_z: float = max(0.1, default_ground_size.z * 0.5)
	polygon.append(Vector2(-half_x, -half_z))
	polygon.append(Vector2(half_x, -half_z))
	polygon.append(Vector2(half_x, half_z))
	polygon.append(Vector2(-half_x, half_z))
	return polygon


func _desired_building_count(profile, legacy_density: int, polygon: PackedVector2Array) -> int:
	if profile == null:
		return max(0, legacy_density)
	var area_world2: float = _polygon_area_abs(polygon)
	var area_m2: float = area_world2 / max(
		0.000001,
		world_units_per_meter * world_units_per_meter
	)
	var coverage := clampf(float(profile.get("target_coverage_ratio")), 0.0, 0.9)
	var avg_footprint: float = max(1.0, _profile_average_footprint_m2(profile))
	var suggested := int(round((area_m2 * coverage) / avg_footprint))
	if profile.has_method("clamp_building_count"):
		return int(profile.clamp_building_count(suggested))
	var lower: int = max(0, int(profile.get("min_buildings")))
	var upper: int = max(lower, int(profile.get("max_buildings")))
	return clampi(suggested, lower, upper)


func _building_positions(
	profile,
	polygon: PackedVector2Array,
	desired_count: int,
	rng: RandomNumberGenerator
) -> Array[Vector3]:
	if desired_count <= 0 or polygon.size() < 3:
		return []
	var bounds := _polygon_bounds(polygon)
	var avg_footprint_m2: float = _profile_average_footprint_m2(profile)
	var spacing_m: float = building_spacing / max(0.0001, world_units_per_meter)
	var setback_m := 0.0
	var jitter_m: float = 0.5 / max(0.0001, world_units_per_meter)
	var fill_ratio := 0.72
	var pattern := "grid_jittered"
	if profile != null:
		pattern = str(profile.get("placement_pattern"))
		fill_ratio = clampf(float(profile.get("min_fill_ratio")), 0.1, 1.0)
		spacing_m = max(
			1.0,
			sqrt(avg_footprint_m2)
			+ max(0.0, float(profile.get("building_spacing_m")))
		)
		var boundary_setback_m := float(profile.get("boundary_setback_m"))
		var road_setback_m := float(profile.get("road_setback_m"))
		setback_m = max(0.0, max(boundary_setback_m, road_setback_m))
		jitter_m = max(0.0, float(profile.get("grid_jitter_m")))
	var spacing_world: float = max(0.2, spacing_m * world_units_per_meter)
	var setback_world: float = max(0.0, setback_m * world_units_per_meter)
	var jitter_world: float = min(spacing_world * 0.35, jitter_m * world_units_per_meter)
	var min_separation_world: float = max(0.01, spacing_world * 0.42)
	match pattern:
		"organic_random":
			return _random_building_positions(
				polygon,
				bounds,
				desired_count,
				rng,
				setback_world,
				min_separation_world,
				fill_ratio
			)
		"campus_cluster":
			return _clustered_building_positions(
				polygon,
				bounds,
				desired_count,
				rng,
				setback_world,
				min_separation_world,
				fill_ratio,
				2
			)
		"yard_cluster":
			return _clustered_building_positions(
				polygon,
				bounds,
				desired_count,
				rng,
				setback_world,
				min_separation_world,
				fill_ratio,
				3
			)
		_:
			return _jittered_grid_building_positions(
				polygon,
				bounds,
				desired_count,
				rng,
				spacing_world,
				setback_world,
				jitter_world,
				min_separation_world,
				fill_ratio
			)


func _jittered_grid_building_positions(
	polygon: PackedVector2Array,
	bounds: Rect2,
	desired_count: int,
	rng: RandomNumberGenerator,
	spacing_world: float,
	setback_world: float,
	jitter_world: float,
	min_separation_world: float,
	fill_ratio: float
) -> Array[Vector3]:
	var output: Array[Vector3] = []
	var candidates: Array[Vector2] = []
	var row_index := 0
	var y: float = bounds.position.y + spacing_world * 0.5
	var scanned_cells := 0
	var max_scan_cells: int = max(2500, desired_count * 160)
	while y <= bounds.end.y and scanned_cells < max_scan_cells:
		var offset: float = 0.0 if row_index % 2 == 0 else spacing_world * 0.5
		var x: float = bounds.position.x + spacing_world * 0.5 + offset
		while x <= bounds.end.x and scanned_cells < max_scan_cells:
			scanned_cells += 1
			var candidate := Vector2(
				x + rng.randf_range(-jitter_world, jitter_world),
				y + rng.randf_range(-jitter_world, jitter_world)
			)
			if _point_is_buildable(candidate, polygon, setback_world):
				candidates.append(candidate)
			x += spacing_world
		row_index += 1
		y += spacing_world
	candidates.shuffle()
	for candidate in candidates:
		if output.size() >= desired_count:
			break
		if _is_far_enough_from_existing(candidate, output, min_separation_world):
			output.append(Vector3(candidate.x, 0.0, candidate.y))
	output = _ensure_minimum_fill_positions(
		output,
		polygon,
		bounds,
		desired_count,
		rng,
		setback_world,
		min_separation_world,
		fill_ratio
	)
	return output


func _random_building_positions(
	polygon: PackedVector2Array,
	bounds: Rect2,
	desired_count: int,
	rng: RandomNumberGenerator,
	setback_world: float,
	min_separation_world: float,
	fill_ratio: float
) -> Array[Vector3]:
	var output: Array[Vector3] = []
	return _ensure_minimum_fill_positions(
		output,
		polygon,
		bounds,
		desired_count,
		rng,
		setback_world,
		min_separation_world,
		fill_ratio
	)


func _clustered_building_positions(
	polygon: PackedVector2Array,
	bounds: Rect2,
	desired_count: int,
	rng: RandomNumberGenerator,
	setback_world: float,
	min_separation_world: float,
	fill_ratio: float,
	cluster_count: int
) -> Array[Vector3]:
	var output: Array[Vector3] = []
	var centers: Array[Vector2] = []
	var center_attempts: int = max(40, cluster_count * 30)
	while centers.size() < cluster_count and center_attempts > 0:
		center_attempts -= 1
		var candidate := _random_point_in_bounds(bounds, rng)
		if _point_is_buildable(candidate, polygon, setback_world):
			centers.append(candidate)
	var radius: float = max(bounds.size.x, bounds.size.y) * 0.23
	var attempts: int = max(300, desired_count * 90)
	while output.size() < desired_count and attempts > 0 and not centers.is_empty():
		attempts -= 1
		var center := centers[rng.randi_range(0, centers.size() - 1)]
		var candidate := center + Vector2(
			rng.randfn(0.0, radius * 0.35),
			rng.randfn(0.0, radius * 0.35)
		)
		if _point_is_buildable(candidate, polygon, setback_world):
			if _is_far_enough_from_existing(candidate, output, min_separation_world):
				output.append(Vector3(candidate.x, 0.0, candidate.y))
	return _ensure_minimum_fill_positions(
		output,
		polygon,
		bounds,
		desired_count,
		rng,
		setback_world,
		min_separation_world * 0.82,
		fill_ratio
	)


func _ensure_minimum_fill_positions(
	output: Array[Vector3],
	polygon: PackedVector2Array,
	bounds: Rect2,
	desired_count: int,
	rng: RandomNumberGenerator,
	setback_world: float,
	min_separation_world: float,
	fill_ratio: float
) -> Array[Vector3]:
	var minimum_count: int = min(desired_count, max(1, int(ceil(float(desired_count) * fill_ratio))))
	var relaxed_separation := min_separation_world
	var passes := 0
	while output.size() < minimum_count and passes < 4:
		var attempts: int = max(250, desired_count * 80)
		while output.size() < desired_count and attempts > 0:
			attempts -= 1
			var candidate := _random_point_in_bounds(bounds, rng)
			if not _point_is_buildable(candidate, polygon, setback_world):
				continue
			if _is_far_enough_from_existing(candidate, output, relaxed_separation):
				output.append(Vector3(candidate.x, 0.0, candidate.y))
		relaxed_separation *= 0.68
		setback_world *= 0.72
		passes += 1
	if output.size() > desired_count:
		output = output.slice(0, desired_count)
	return output


func _random_point_in_bounds(bounds: Rect2, rng: RandomNumberGenerator) -> Vector2:
	return Vector2(
		rng.randf_range(bounds.position.x, bounds.end.x),
		rng.randf_range(bounds.position.y, bounds.end.y)
	)


func _is_far_enough_from_existing(
	candidate: Vector2,
	existing: Array[Vector3],
	min_distance: float
) -> bool:
	if min_distance <= 0.0001:
		return true
	var min_distance_sq := min_distance * min_distance
	for point in existing:
		var flat := Vector2(point.x, point.z)
		if flat.distance_squared_to(candidate) < min_distance_sq:
			return false
	return true


func _point_is_buildable(point: Vector2, polygon: PackedVector2Array, setback_world: float) -> bool:
	if not Geometry2D.is_point_in_polygon(point, polygon):
		return false
	if setback_world <= 0.0001:
		return true
	return _distance_to_polygon_edges(point, polygon) >= setback_world


func _profile_average_footprint_m2(profile) -> float:
	if profile != null and profile.has_method("average_building_footprint_m2"):
		return float(profile.average_building_footprint_m2())
	if profile != null:
		return max(
			1.0,
			(float(profile.get("min_building_footprint_m2")) + float(profile.get("max_building_footprint_m2"))) * 0.5
		)
	return max(1.0, default_ground_size.x * default_ground_size.z)


func _random_profile_footprint_m2(profile, rng: RandomNumberGenerator) -> float:
	if profile != null and profile.has_method("random_footprint_m2"):
		return float(profile.random_footprint_m2(rng))
	if profile != null:
		var lower: float = max(1.0, float(profile.get("min_building_footprint_m2")))
		var upper: float = max(lower, float(profile.get("max_building_footprint_m2")))
		return rng.randf_range(lower, upper)
	return 80.0


func _random_profile_floor_count(profile, rng: RandomNumberGenerator) -> int:
	if profile != null and profile.has_method("random_floor_count"):
		return int(profile.random_floor_count(rng))
	if profile != null:
		var lower: int = max(1, int(profile.get("min_floors")))
		var upper: int = max(lower, int(profile.get("max_floors")))
		return rng.randi_range(lower, upper)
	return rng.randi_range(1, 4)


func _building_rotation_y(
	profile,
	base_rotation_y: float,
	rng: RandomNumberGenerator,
	index: int
) -> float:
	if profile == null:
		return _snap_right_angle(base_rotation_y) + rng.randf_range(-0.04, 0.04)
	var strategy := str(profile.get("rotation_strategy"))
	var jitter := deg_to_rad(max(0.0, float(profile.get("rotation_jitter_degrees"))))
	if strategy == "random":
		return rng.randf_range(-PI, PI)
	var rotation := _snap_right_angle(base_rotation_y)
	var perpendicular_probability := clampf(
		float(profile.get("perpendicular_rotation_probability")),
		0.0,
		1.0
	)
	if strategy == "perpendicular_mix":
		var rotate_perpendicular := rng.randf() < perpendicular_probability
		if rotate_perpendicular:
			rotation += PI * 0.5
		elif index % 7 == 0:
			rotation += PI
	rotation += rng.randf_range(-jitter, jitter)
	return rotation


func _dominant_polygon_rotation_y(polygon: PackedVector2Array) -> float:
	if polygon.size() < 2:
		return 0.0
	var best_direction := Vector2.RIGHT
	var best_length_sq := 0.0
	for index in range(polygon.size()):
		var start := polygon[index]
		var end := polygon[(index + 1) % polygon.size()]
		var direction := end - start
		var length_sq := direction.length_squared()
		if length_sq > best_length_sq:
			best_length_sq = length_sq
			best_direction = direction
	if best_length_sq <= 0.000001:
		return 0.0
	return atan2(best_direction.x, best_direction.y)


func _snap_right_angle(angle: float) -> float:
	var quarter_turn := PI * 0.5
	return round(angle / quarter_turn) * quarter_turn


func _asset_scale_multiplier(
	profile,
	target_footprint_m2: float,
	rng: RandomNumberGenerator,
	building: Node3D = null
) -> float:
	var legacy_scale := rng.randf_range(min_building_scale, max_building_scale)
	var lower := 0.01
	var upper := 8.0
	if profile != null:
		lower = max(0.01, float(profile.get("min_asset_scale_multiplier")))
		upper = max(lower, float(profile.get("max_asset_scale_multiplier")))
	if building != null:
		var current_side_world := _node_local_footprint_side(building)
		if current_side_world > 0.0001:
			var target_side_world := sqrt(max(1.0, target_footprint_m2)) * world_units_per_meter
			return clampf((target_side_world / current_side_world) * legacy_scale, lower, upper)
	if profile == null:
		return legacy_scale
	var nominal: float = max(1.0, float(profile.get("nominal_asset_footprint_m2")))
	var footprint_scale: float = sqrt(max(1.0, target_footprint_m2) / nominal)
	return clampf(footprint_scale * legacy_scale, lower, upper)


func _polygon_area_abs(polygon: PackedVector2Array) -> float:
	var area := 0.0
	for index in range(polygon.size()):
		var current := polygon[index]
		var next := polygon[(index + 1) % polygon.size()]
		area += current.x * next.y - next.x * current.y
	return abs(area) * 0.5


func _polygon_bounds(polygon: PackedVector2Array) -> Rect2:
	if polygon.is_empty():
		return Rect2(Vector2.ZERO, Vector2.ONE)
	var min_point := polygon[0]
	var max_point := polygon[0]
	for point in polygon:
		min_point.x = min(min_point.x, point.x)
		min_point.y = min(min_point.y, point.y)
		max_point.x = max(max_point.x, point.x)
		max_point.y = max(max_point.y, point.y)
	return Rect2(min_point, max_point - min_point)


func _distance_to_polygon_edges(point: Vector2, polygon: PackedVector2Array) -> float:
	if polygon.size() < 2:
		return 0.0
	var best := INF
	for index in range(polygon.size()):
		var start := polygon[index]
		var end := polygon[(index + 1) % polygon.size()]
		best = min(best, _distance_to_segment(point, start, end))
	return best


func _distance_to_segment(point: Vector2, start: Vector2, end: Vector2) -> float:
	var segment := end - start
	var length_sq := segment.length_squared()
	if length_sq <= 0.000001:
		return point.distance_to(start)
	var t := clampf((point - start).dot(segment) / length_sq, 0.0, 1.0)
	return point.distance_to(start + segment * t)


func _node_local_min_y(node: Node3D) -> float:
	return _node_local_min_y_with_transform(node, Transform3D.IDENTITY)


func _align_node_bottom_to_ground(node: Node3D, ground_clearance: float) -> void:
	var current_min_y := _node_local_min_y(node)
	var target_min_y: float = max(0.0, ground_clearance)
	node.position.y += target_min_y - current_min_y


func _node_local_min_y_with_transform(node: Node3D, parent_transform: Transform3D) -> float:
	var min_y := INF
	var current_transform := parent_transform * node.transform
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			var aabb := mesh_instance.mesh.get_aabb()
			for corner in _aabb_corners(aabb):
				var transformed := current_transform * corner
				min_y = min(min_y, transformed.y)
	for child in node.get_children():
		if child is Node3D:
			var child_min := _node_local_min_y_with_transform(child as Node3D, current_transform)
			if child_min < INF:
				min_y = min(min_y, child_min)
	return 0.0 if min_y == INF else min_y


func _node_local_footprint_side(node: Node3D) -> float:
	var bounds := _node_local_xz_bounds_with_transform(node, Transform3D.IDENTITY)
	if not bool(bounds.get("has_bounds", false)):
		return 0.0
	var width: float = float(bounds.get("max_x")) - float(bounds.get("min_x"))
	var depth: float = float(bounds.get("max_z")) - float(bounds.get("min_z"))
	return max(width, depth)


func _node_local_xz_bounds_with_transform(node: Node3D, parent_transform: Transform3D) -> Dictionary:
	var result := {
		"has_bounds": false,
		"min_x": INF,
		"max_x": -INF,
		"min_z": INF,
		"max_z": -INF,
	}
	var current_transform := parent_transform * node.transform
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			for corner in _aabb_corners(mesh_instance.mesh.get_aabb()):
				var transformed := current_transform * corner
				result["has_bounds"] = true
				result["min_x"] = min(float(result["min_x"]), transformed.x)
				result["max_x"] = max(float(result["max_x"]), transformed.x)
				result["min_z"] = min(float(result["min_z"]), transformed.z)
				result["max_z"] = max(float(result["max_z"]), transformed.z)
	for child in node.get_children():
		if child is Node3D:
			var child_bounds := _node_local_xz_bounds_with_transform(child as Node3D, current_transform)
			if bool(child_bounds.get("has_bounds", false)):
				result["has_bounds"] = true
				result["min_x"] = min(float(result["min_x"]), float(child_bounds.get("min_x")))
				result["max_x"] = max(float(result["max_x"]), float(child_bounds.get("max_x")))
				result["min_z"] = min(float(result["min_z"]), float(child_bounds.get("min_z")))
				result["max_z"] = max(float(result["max_z"]), float(child_bounds.get("max_z")))
	return result


func _aabb_corners(aabb: AABB) -> Array[Vector3]:
	var position := aabb.position
	var size := aabb.size
	return [
		position,
		position + Vector3(size.x, 0.0, 0.0),
		position + Vector3(0.0, size.y, 0.0),
		position + Vector3(0.0, 0.0, size.z),
		position + Vector3(size.x, size.y, 0.0),
		position + Vector3(size.x, 0.0, size.z),
		position + Vector3(0.0, size.y, size.z),
		position + size,
	]


func _apply_material_recursive(node: Node, material: Material) -> void:
	if node is MeshInstance3D:
		(node as MeshInstance3D).set_surface_override_material(0, material)
	for child in node.get_children():
		_apply_material_recursive(child, material)


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_")


func _request_zone_refresh() -> void:
	if not is_inside_tree():
		return
	call_deferred("_refresh_zone_visuals")


func _effective_zone_entry():
	if _configured_zone_entry != null:
		return _configured_zone_entry
	if not Engine.is_editor_hint():
		return null
	if preview_catalog_path.is_empty():
		return null
	var resource := load(preview_catalog_path)
	if resource != null and resource.has_method("entry_for_zone_type"):
		return resource.entry_for_zone_type(default_zone_type)
	return null


func _ground_node() -> MeshInstance3D:
	if ground != null:
		return ground
	return get_node_or_null("ZoneGround") as MeshInstance3D


func _label_node() -> Label3D:
	if label != null:
		return label
	return get_node_or_null("ZoneLabel") as Label3D


func _building_cluster_root_node() -> Node3D:
	if building_cluster_root != null:
		return building_cluster_root
	return get_node_or_null("BuildingClusterRoot") as Node3D
