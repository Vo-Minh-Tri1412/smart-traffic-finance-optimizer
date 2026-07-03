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
@export var seed := 17:
	set(value):
		seed = value
		_request_zone_refresh()
@export var label_prefix := "":
	set(value):
		label_prefix = value
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
	var active_building_scenes: Array = []
	var density := building_density
	var min_scale := min_building_scale
	var max_scale := max_building_scale
	var active_building_asset_scale := building_asset_scale
	var active_building_asset_offset := building_asset_offset
	var active_building_ground_clearance := building_ground_clearance
	var active_building_override_material: Material = building_override_material
	var active_seed := seed + zone_id.length() * 97
	var scene_has_building_assets := not building_scenes.is_empty() or not building_scene_paths.is_empty()
	if scene_has_building_assets:
		active_building_scenes.append_array(building_scenes)
		for scene_path in building_scene_paths:
			var loaded_scene: Resource = load(str(scene_path))
			if loaded_scene is PackedScene:
				active_building_scenes.append(loaded_scene)
	elif zone_entry != null:
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
		active_seed += int(zone_entry.get("seed"))

	var rng := RandomNumberGenerator.new()
	rng.seed = active_seed
	var count: int = max(1, density)
	for index in range(count):
		var building: Node3D = _instantiate_building(
			active_building_scenes,
			index,
			active_building_asset_scale,
			active_building_asset_offset,
			active_building_ground_clearance,
			active_building_override_material
		)
		if building == null:
			continue
		var column := index % 3
		var row := int(index / 3)
		var jitter := Vector3(rng.randf_range(-0.25, 0.25), 0.0, rng.randf_range(-0.25, 0.25))
		building.position = Vector3(
			(float(column) - 1.0) * building_spacing,
			0.0,
			(float(row) - 0.5) * building_spacing
		) + jitter
		var scalar := rng.randf_range(min_scale, max_scale)
		building.scale *= scalar
		building.rotation.y = rng.randf_range(-0.25, 0.25)
		cluster_root.add_child(building)


func _instantiate_building(
	building_scenes: Array,
	index: int,
	building_asset_scale: float,
	building_asset_offset: Vector3,
	building_ground_clearance: float,
	building_override_material: Material
) -> Node3D:
	if not building_scenes.is_empty():
		var raw_scene = building_scenes[index % building_scenes.size()]
		if raw_scene is PackedScene:
			var instance = (raw_scene as PackedScene).instantiate()
			if instance is Node3D:
				var wrapper := Node3D.new()
				wrapper.name = "BuildingAsset_%d" % index
				wrapper.scale = Vector3.ONE * max(0.001, building_asset_scale)
				wrapper.position = Vector3(0.0, building_ground_clearance, 0.0) + building_asset_offset
				wrapper.add_child(instance as Node3D)
				if building_override_material != null:
					_apply_material_recursive(wrapper, building_override_material)
				return wrapper
			if instance != null:
				instance.queue_free()
	var placeholder := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.7, 1.2 + 0.3 * float(index % 3), 0.7)
	placeholder.mesh = mesh
	placeholder.position = Vector3(0.0, mesh.size.y / 2.0 + building_ground_clearance, 0.0) + building_asset_offset
	var material := StandardMaterial3D.new()
	material.albedo_color = default_zone_color.lightened(0.25)
	placeholder.set_surface_override_material(0, material)
	return placeholder


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
