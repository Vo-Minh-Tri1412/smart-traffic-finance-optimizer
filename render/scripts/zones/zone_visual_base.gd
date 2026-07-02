class_name ZoneVisualBase
extends Node3D

@onready var ground: MeshInstance3D = $ZoneGround
@onready var label: Label3D = $ZoneLabel
@onready var building_cluster_root: Node3D = $BuildingClusterRoot

@export var default_zone_type := "mixed"
@export var default_zone_color := Color(0.2, 0.7, 0.35, 0.32)
@export var default_ground_size := Vector3(5.0, 0.08, 5.0)
@export var building_spacing := 1.45

var zone_id := ""
var zone_type := ""
var display_name := ""
var _configured_zone_entry = null


func configure_zone(zone_data: Dictionary, zone_entry = null) -> void:
	zone_id = str(zone_data.get("id", ""))
	zone_type = str(zone_data.get("type", zone_data.get("zone_type", default_zone_type)))
	display_name = str(zone_data.get("name", zone_data.get("display_name", zone_id)))
	name = _safe_node_name("Zone_%s" % (zone_id if not zone_id.is_empty() else zone_type))
	_configured_zone_entry = zone_entry
	if is_node_ready():
		_refresh_zone_visuals()


func _ready() -> void:
	if zone_type.is_empty():
		zone_type = default_zone_type
	_refresh_zone_visuals()


func _refresh_zone_visuals() -> void:
	_apply_label(_configured_zone_entry)
	_apply_ground(_configured_zone_entry)
	_build_building_cluster(_configured_zone_entry)


func _apply_label(zone_entry) -> void:
	if label == null:
		return
	var prefix := ""
	if zone_entry != null:
		prefix = str(zone_entry.get("label_prefix"))
	label.text = "%s%s" % [prefix, display_name if not display_name.is_empty() else zone_type]


func _apply_ground(zone_entry) -> void:
	if ground == null:
		return
	var mesh := ground.mesh
	if mesh is BoxMesh:
		(mesh as BoxMesh).size = default_ground_size
	var material = zone_entry.get("ground_material") if zone_entry != null else null
	if material is Material:
		ground.set_surface_override_material(0, material)
	else:
		var fallback := StandardMaterial3D.new()
		fallback.albedo_color = default_zone_color
		fallback.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		ground.set_surface_override_material(0, fallback)


func _build_building_cluster(zone_entry) -> void:
	if building_cluster_root == null:
		return
	for child in building_cluster_root.get_children():
		child.queue_free()
	var building_scenes: Array = []
	var density := 3
	var min_scale := 0.8
	var max_scale := 1.25
	var building_asset_scale := 0.05
	var seed := 17 + zone_id.length() * 97
	if zone_entry != null:
		var raw_building_scenes = zone_entry.get("building_scenes")
		if raw_building_scenes is Array:
			building_scenes = raw_building_scenes as Array
		var raw_building_scene_paths = zone_entry.get("building_scene_paths")
		if raw_building_scene_paths is PackedStringArray:
			for scene_path in raw_building_scene_paths:
				var loaded_scene: Resource = load(str(scene_path))
				if loaded_scene is PackedScene:
					building_scenes.append(loaded_scene)
		density = max(0, int(zone_entry.get("building_density")))
		min_scale = float(zone_entry.get("min_building_scale"))
		max_scale = float(zone_entry.get("max_building_scale"))
		building_asset_scale = float(zone_entry.get("building_asset_scale"))
		seed += int(zone_entry.get("seed"))

	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var count: int = max(1, density)
	for index in range(count):
		var building: Node3D = _instantiate_building(building_scenes, index, building_asset_scale)
		if building == null:
			continue
		var column := index % 3
		var row := int(index / 3)
		var jitter := Vector3(rng.randf_range(-0.25, 0.25), 0.0, rng.randf_range(-0.25, 0.25))
		building.position = Vector3(
			(float(column) - 1.0) * building_spacing,
			0.1,
			(float(row) - 0.5) * building_spacing
		) + jitter
		var scalar := rng.randf_range(min_scale, max_scale)
		building.scale *= scalar
		building.rotation.y = rng.randf_range(-0.25, 0.25)
		building_cluster_root.add_child(building)


func _instantiate_building(building_scenes: Array, index: int, building_asset_scale: float) -> Node3D:
	if not building_scenes.is_empty():
		var raw_scene = building_scenes[index % building_scenes.size()]
		if raw_scene is PackedScene:
			var instance = (raw_scene as PackedScene).instantiate()
			if instance is Node3D:
				var wrapper := Node3D.new()
				wrapper.name = "BuildingAsset_%d" % index
				wrapper.scale = Vector3.ONE * max(0.001, building_asset_scale)
				wrapper.add_child(instance as Node3D)
				return wrapper
			if instance != null:
				instance.queue_free()
	var placeholder := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.7, 1.2 + 0.3 * float(index % 3), 0.7)
	placeholder.mesh = mesh
	placeholder.position.y = mesh.size.y / 2.0
	var material := StandardMaterial3D.new()
	material.albedo_color = default_zone_color.lightened(0.25)
	placeholder.set_surface_override_material(0, material)
	return placeholder


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_")
