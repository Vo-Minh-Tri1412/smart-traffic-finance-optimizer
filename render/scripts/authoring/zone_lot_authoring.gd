@tool
class_name ZoneLotAuthoring
extends Node3D

@export var zone_id := "zone_001":
	set(value):
		zone_id = value
		_request_rebuild()
@export_enum("residential", "commercial", "hospital", "school", "industrial", "gateway", "nightlife")
var zone_type := "residential":
	set(value):
		zone_type = value
		_request_rebuild()
@export var display_name := "Zone":
	set(value):
		display_name = value
		_request_rebuild()
@export var lot_size := Vector2(8.0, 8.0):
	set(value):
		lot_size = value
		_request_rebuild()
@export var zone_catalog_path := "res://resources/catalogs/ZoneAssetCatalog.tres":
	set(value):
		zone_catalog_path = value
		_request_rebuild()
@export var custom_building_scenes: Array[PackedScene] = []:
	set(value):
		custom_building_scenes = value
		_request_rebuild()
@export_range(0, 30, 1) var building_count := 5:
	set(value):
		building_count = value
		_request_rebuild()
@export var building_asset_scale := 0.32:
	set(value):
		building_asset_scale = value
		_request_rebuild()
@export var placeholder_building_scale := Vector3(0.9, 2.4, 0.9):
	set(value):
		placeholder_building_scale = value
		_request_rebuild()
@export var show_ground := true:
	set(value):
		show_ground = value
		_request_rebuild()
@export var show_label := true:
	set(value):
		show_label = value
		_request_rebuild()
@export var random_seed := 1001:
	set(value):
		random_seed = value
		_request_rebuild()
@export var rebuild_preview := false:
	set(value):
		rebuild_preview = false
		_request_rebuild()

var _rebuild_queued := false


func _ready() -> void:
	_request_rebuild()


func _request_rebuild() -> void:
	if not is_inside_tree():
		return
	if _rebuild_queued:
		return
	_rebuild_queued = true
	call_deferred("_rebuild_preview")


func _rebuild_preview() -> void:
	_rebuild_queued = false
	_clear_generated()
	var entry = _catalog_entry()
	if show_ground:
		_add_ground(entry)
		_add_border()
	if show_label:
		_add_label(entry)
	_add_buildings(entry)


func building_visual_count() -> int:
	var root := get_node_or_null("GeneratedBuildings")
	return root.get_child_count() if root != null else 0


func summary() -> Dictionary:
	return {
		"zone_id": zone_id,
		"zone_type": zone_type,
		"display_name": display_name,
		"building_visual_count": building_visual_count(),
		"uses_custom_assets": not custom_building_scenes.is_empty(),
	}


func _catalog_entry():
	var catalog = load(zone_catalog_path)
	if catalog != null and catalog.has_method("entry_for_zone_type"):
		return catalog.entry_for_zone_type(zone_type)
	return null


func _building_scenes(entry) -> Array:
	if not custom_building_scenes.is_empty():
		return custom_building_scenes
	var scenes: Array = []
	if entry == null:
		return scenes
	var raw_scenes = entry.get("building_scenes")
	if raw_scenes is Array:
		for scene in raw_scenes:
			if scene is PackedScene:
				scenes.append(scene)
	var raw_paths = entry.get("building_scene_paths")
	if raw_paths is PackedStringArray:
		for scene_path in raw_paths:
			var loaded = load(str(scene_path))
			if loaded is PackedScene:
				scenes.append(loaded)
	return scenes


func _add_ground(entry) -> void:
	var ground := MeshInstance3D.new()
	ground.name = "GeneratedZoneGround"
	var mesh := BoxMesh.new()
	mesh.size = Vector3(max(0.1, lot_size.x), 0.08, max(0.1, lot_size.y))
	ground.mesh = mesh
	ground.position = Vector3(0.0, 0.04, 0.0)
	var material = entry.get("ground_material") if entry != null else null
	if material is Material:
		ground.set_surface_override_material(0, material)
	else:
		var color := _zone_color()
		color.a = 0.34
		ground.set_surface_override_material(0, _material(color, true))
	_mark_generated(ground)
	add_child(ground)


func _add_border() -> void:
	var border_color := Color(1.0, 1.0, 1.0, 0.82)
	var half_x := lot_size.x / 2.0
	var half_z := lot_size.y / 2.0
	_add_border_strip("Border_N", Vector3(0.0, 0.13, -half_z), Vector3(lot_size.x, 0.025, 0.08), border_color)
	_add_border_strip("Border_S", Vector3(0.0, 0.13, half_z), Vector3(lot_size.x, 0.025, 0.08), border_color)
	_add_border_strip("Border_W", Vector3(-half_x, 0.13, 0.0), Vector3(0.08, 0.025, lot_size.y), border_color)
	_add_border_strip("Border_E", Vector3(half_x, 0.13, 0.0), Vector3(0.08, 0.025, lot_size.y), border_color)


func _add_border_strip(strip_name: String, strip_position: Vector3, strip_size: Vector3, color: Color) -> void:
	var strip := MeshInstance3D.new()
	strip.name = strip_name
	var mesh := BoxMesh.new()
	mesh.size = strip_size
	strip.mesh = mesh
	strip.position = strip_position
	strip.set_surface_override_material(0, _material(color, true))
	_mark_generated(strip)
	add_child(strip)


func _add_label(entry) -> void:
	var label := Label3D.new()
	label.name = "GeneratedZoneLabel"
	var prefix := ""
	if entry != null:
		prefix = str(entry.get("label_prefix"))
	label.text = "%s%s" % [prefix, display_name]
	label.font_size = 34
	label.pixel_size = 0.018
	label.outline_size = 8
	label.position = Vector3(0.0, 2.8, -lot_size.y / 2.0 - 0.7)
	label.rotation_degrees = Vector3(-28.0, 0.0, 0.0)
	_mark_generated(label)
	add_child(label)


func _add_buildings(entry) -> void:
	var root := Node3D.new()
	root.name = "GeneratedBuildings"
	_mark_generated(root)
	add_child(root)

	var scenes := _building_scenes(entry)
	var rng := RandomNumberGenerator.new()
	rng.seed = random_seed + zone_id.hash()
	var columns: int = max(1, int(ceil(sqrt(float(max(1, building_count))))))
	var usable_x: float = max(1.0, lot_size.x - 2.0)
	var usable_z: float = max(1.0, lot_size.y - 2.0)
	for index in range(building_count):
		var building := _create_building(index, scenes)
		if building == null:
			continue
		var column: int = index % columns
		var row: int = int(index / columns)
		var x: float = -usable_x / 2.0 + usable_x * (float(column) + 0.5) / float(columns)
		var z: float = -usable_z / 2.0 + usable_z * (float(row) + 0.5) / float(columns)
		building.position = Vector3(
			x + rng.randf_range(-0.25, 0.25),
			0.2,
			z + rng.randf_range(-0.25, 0.25)
		)
		building.rotation_degrees.y = rng.randf_range(-16.0, 16.0)
		root.add_child(building)


func _create_building(index: int, scenes: Array) -> Node3D:
	if not scenes.is_empty():
		var scene = scenes[index % scenes.size()]
		if scene is PackedScene:
			var instance = (scene as PackedScene).instantiate()
			if instance is Node3D:
				var wrapper := Node3D.new()
				wrapper.name = "BuildingAsset_%02d" % index
				wrapper.scale = Vector3.ONE * max(0.001, building_asset_scale)
				wrapper.add_child(instance as Node3D)
				return wrapper
			if instance != null:
				instance.queue_free()

	var placeholder := MeshInstance3D.new()
	placeholder.name = "BuildingPlaceholder_%02d" % index
	var mesh := BoxMesh.new()
	mesh.size = Vector3(
		placeholder_building_scale.x,
		placeholder_building_scale.y * (1.0 + 0.25 * float(index % 3)),
		placeholder_building_scale.z
	)
	placeholder.mesh = mesh
	placeholder.position.y = mesh.size.y / 2.0
	placeholder.set_surface_override_material(0, _material(_zone_color().lightened(0.22), false))
	return placeholder


func _clear_generated() -> void:
	for child in get_children():
		if child.is_in_group("zone_lot_authoring_generated"):
			child.queue_free()


func _mark_generated(node: Node) -> void:
	node.add_to_group("zone_lot_authoring_generated")


func _zone_color() -> Color:
	match zone_type:
		"residential":
			return Color(0.25, 0.78, 0.38, 0.38)
		"hospital":
			return Color(0.95, 0.30, 0.30, 0.38)
		"industrial":
			return Color(0.72, 0.46, 0.25, 0.38)
		"commercial":
			return Color(0.25, 0.45, 0.82, 0.38)
		"school":
			return Color(0.95, 0.72, 0.25, 0.38)
		"gateway":
			return Color(0.55, 0.45, 0.78, 0.38)
		"nightlife":
			return Color(0.78, 0.25, 0.72, 0.38)
		_:
			return Color(0.5, 0.7, 0.5, 0.38)


func _material(color: Color, transparent: bool) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	if transparent:
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return material
