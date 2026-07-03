extends RefCounted

const VehicleAssetRegistryScript := preload("res://scripts/assets/vehicle_asset_registry.gd")

var registry = VehicleAssetRegistryScript.new()
var fallback_spawn_count := 0
var created_vehicle_count := 0


func configure(manifest_path: String) -> bool:
	fallback_spawn_count = 0
	created_vehicle_count = 0
	return registry.load_manifest(manifest_path)


func create_vehicle(vehicle_type: String, vehicle_id: String = "") -> Node3D:
	var scene_path := registry.scene_path_for_vehicle_type(vehicle_type)
	if scene_path == registry.fallback_vehicle_scene_path():
		fallback_spawn_count += 1

	var scene: PackedScene = registry.scene_for_vehicle_type(vehicle_type)
	if scene == null:
		return null

	var node := scene.instantiate()
	if not (node is Node3D):
		push_error("Vehicle scene for %s does not instantiate a Node3D." % vehicle_type)
		node.queue_free()
		return null

	var vehicle_node := node as Node3D
	if vehicle_node.has_method("configure"):
		vehicle_node.configure(vehicle_type, vehicle_id)
	else:
		vehicle_node.name = _safe_node_name(vehicle_id if not vehicle_id.is_empty() else vehicle_type)
	_attach_catalog_visual_asset(vehicle_node, vehicle_type)
	created_vehicle_count += 1
	return vehicle_node


func registered_vehicle_type_count() -> int:
	return registry.registered_vehicle_type_count()


func manifest_loaded() -> bool:
	return registry.errors.is_empty() and registry.registered_vehicle_type_count() > 0


func errors() -> Array[String]:
	return registry.errors


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_")


func _attach_catalog_visual_asset(vehicle_node: Node3D, vehicle_type: String) -> void:
	if vehicle_node.get_node_or_null("VisualAsset") != null:
		return
	if (
		vehicle_node.has_method("has_scene_visual_asset_configured")
		and vehicle_node.has_scene_visual_asset_configured()
	):
		return
	var visual_asset_scene := registry.visual_asset_scene_for_vehicle_type(vehicle_type)
	if visual_asset_scene == null:
		return
	if vehicle_node.has_method("apply_external_visual_asset"):
		vehicle_node.apply_external_visual_asset(
			visual_asset_scene,
			registry.visual_asset_scale_for_vehicle_type(vehicle_type),
			registry.visual_asset_offset_for_vehicle_type(vehicle_type),
			registry.visual_asset_rotation_degrees_for_vehicle_type(vehicle_type),
			registry.hide_base_body_for_vehicle_type(vehicle_type)
		)
		return
	var instance := visual_asset_scene.instantiate()
	if not (instance is Node3D):
		if instance != null:
			instance.queue_free()
		push_warning("Vehicle visual asset for %s did not instantiate a Node3D." % vehicle_type)
		return
	var visual_asset := instance as Node3D
	visual_asset.name = "VisualAsset"
	visual_asset.scale = registry.visual_asset_scale_for_vehicle_type(vehicle_type)
	visual_asset.position = registry.visual_asset_offset_for_vehicle_type(vehicle_type)
	visual_asset.rotation_degrees = registry.visual_asset_rotation_degrees_for_vehicle_type(vehicle_type)
	vehicle_node.add_child(visual_asset)
	if registry.hide_base_body_for_vehicle_type(vehicle_type):
		var body := vehicle_node.get_node_or_null("Body")
		if body is Node3D:
			(body as Node3D).visible = false
