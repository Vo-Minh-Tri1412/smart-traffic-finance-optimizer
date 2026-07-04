@tool
class_name TrafficLightVisualBase
extends Node3D

@export var traffic_light_id := ""
@export var signal_state := "red":
	set(value):
		signal_state = value
		_apply_signal_state()
@export var visual_asset_scene: PackedScene:
	set(value):
		visual_asset_scene = value
		_rebuild_preview_if_needed()
@export var visual_asset_scale := 0.04:
	set(value):
		visual_asset_scale = max(0.001, value)
		_rebuild_preview_if_needed()
@export var pole_height := 1.8:
	set(value):
		pole_height = max(0.2, value)
		_rebuild_preview_if_needed()
@export var lamp_radius := 0.12:
	set(value):
		lamp_radius = max(0.03, value)
		_rebuild_preview_if_needed()
@export var red_material: Material:
	set(value):
		red_material = value
		_apply_signal_state()
@export var yellow_material: Material:
	set(value):
		yellow_material = value
		_apply_signal_state()
@export var green_material: Material:
	set(value):
		green_material = value
		_apply_signal_state()
@export var inactive_material: Material:
	set(value):
		inactive_material = value
		_apply_signal_state()
@export var rebuild_preview := false:
	set(value):
		rebuild_preview = false
		if value:
			_rebuild_visuals()


func _ready() -> void:
	_rebuild_visuals()


func configure_traffic_light(id: String, entry = null) -> void:
	traffic_light_id = id
	name = "TrafficLight_%s" % _safe_name(id)
	if entry != null:
		if entry.get("visual_scene") is PackedScene:
			visual_asset_scene = entry.get("visual_scene") as PackedScene
		elif entry.get("pole_asset_scene") is PackedScene:
			visual_asset_scene = entry.get("pole_asset_scene") as PackedScene
		visual_asset_scale = float(entry.get("asset_scale"))
		pole_height = float(entry.get("pole_height"))
		lamp_radius = float(entry.get("lamp_radius"))
		if entry.get("red_material") is Material:
			red_material = entry.get("red_material") as Material
		if entry.get("yellow_material") is Material:
			yellow_material = entry.get("yellow_material") as Material
		if entry.get("green_material") is Material:
			green_material = entry.get("green_material") as Material
		if entry.get("inactive_material") is Material:
			inactive_material = entry.get("inactive_material") as Material
	_rebuild_visuals()


func set_signal_state(state: String) -> void:
	signal_state = state


func _rebuild_preview_if_needed() -> void:
	if is_inside_tree():
		call_deferred("_rebuild_visuals")


func _rebuild_visuals() -> void:
	_clear_children()
	if visual_asset_scene != null:
		var asset = visual_asset_scene.instantiate()
		if asset is Node3D:
			var asset_node := asset as Node3D
			asset_node.name = "PoleAsset"
			asset_node.scale = Vector3.ONE * visual_asset_scale
			add_child(asset_node)
			_set_editor_owner(asset_node)
		elif asset != null:
			asset.queue_free()
	_build_lamps()
	_apply_signal_state()


func _build_lamps() -> void:
	var lamp_root := Node3D.new()
	lamp_root.name = "SignalLamps"
	lamp_root.position = Vector3(0.0, pole_height, 0.0)
	add_child(lamp_root)
	_set_editor_owner(lamp_root)
	var names := ["red", "yellow", "green"]
	for index in range(names.size()):
		var lamp := MeshInstance3D.new()
		lamp.name = "Lamp_%s" % names[index]
		var mesh := SphereMesh.new()
		mesh.radius = lamp_radius
		mesh.height = lamp_radius * 2.0
		lamp.mesh = mesh
		lamp.position = Vector3(0.0, -float(index) * lamp_radius * 2.5, 0.0)
		lamp_root.add_child(lamp)
		_set_editor_owner(lamp)


func _apply_signal_state() -> void:
	var lamp_root := get_node_or_null("SignalLamps")
	if lamp_root == null:
		return
	var active := _canonical_state(signal_state)
	_apply_lamp_material(lamp_root.get_node_or_null("Lamp_red"), red_material, active == "red")
	_apply_lamp_material(lamp_root.get_node_or_null("Lamp_yellow"), yellow_material, active == "yellow")
	_apply_lamp_material(lamp_root.get_node_or_null("Lamp_green"), green_material, active == "green")


func _apply_lamp_material(node: Node, material: Material, enabled: bool) -> void:
	if not (node is MeshInstance3D):
		return
	var mesh_node := node as MeshInstance3D
	var selected := material if enabled and material != null else inactive_material
	if selected == null:
		selected = _fallback_material(_state_color(mesh_node.name, enabled))
	mesh_node.set_surface_override_material(0, selected)


func _state_color(name_value: String, enabled: bool) -> Color:
	if not enabled:
		return Color(0.08, 0.08, 0.08)
	if name_value.ends_with("red"):
		return Color(1.0, 0.05, 0.04)
	if name_value.ends_with("yellow"):
		return Color(1.0, 0.82, 0.05)
	return Color(0.05, 0.9, 0.18)


func _fallback_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = 0.6
	return material


func _canonical_state(value: String) -> String:
	var lower := value.to_lower()
	if lower.begins_with("g"):
		return "green"
	if lower.begins_with("y"):
		return "yellow"
	return "red"


func _clear_children() -> void:
	for child in get_children():
		remove_child(child)
		child.queue_free()


func _set_editor_owner(node: Node) -> void:
	if not Engine.is_editor_hint() or get_tree() == null:
		return
	var edited_root := get_tree().edited_scene_root
	if edited_root != null:
		node.owner = edited_root


func _safe_name(value: String) -> String:
	return value.replace(":", "_").replace("/", "_").replace(".", "_")
