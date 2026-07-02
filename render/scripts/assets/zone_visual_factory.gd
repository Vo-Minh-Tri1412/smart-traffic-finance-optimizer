extends RefCounted

const DEFAULT_FALLBACK_ZONE_SCENE := "res://scenes/zones/ZoneVisualBase.tscn"

var catalog = null
var catalog_path := ""
var fallback_spawn_count := 0
var created_zone_count := 0
var errors: Array[String] = []


func configure(path: String) -> bool:
	catalog_path = path
	fallback_spawn_count = 0
	created_zone_count = 0
	errors.clear()

	if path.is_empty():
		errors.append("Zone asset catalog path is empty.")
		return false
	var resource := load(path)
	if resource == null or not resource.has_method("entry_for_zone_type"):
		errors.append("Zone asset catalog not found or invalid: %s" % path)
		return false
	catalog = resource
	return true


func create_zone(zone_data: Dictionary) -> Node3D:
	var zone_type := str(zone_data.get("type", zone_data.get("zone_type", "mixed")))
	var entry = catalog.entry_for_zone_type(zone_type) if catalog != null else null
	var scene = catalog.scene_for_zone_type(zone_type) if catalog != null else null
	if scene == null:
		scene = load(DEFAULT_FALLBACK_ZONE_SCENE)
		fallback_spawn_count += 1
	elif entry == null:
		fallback_spawn_count += 1

	if not (scene is PackedScene):
		errors.append("No PackedScene available for zone type %s." % zone_type)
		return null

	var node = (scene as PackedScene).instantiate()
	if not (node is Node3D):
		errors.append("Zone scene for %s does not instantiate Node3D." % zone_type)
		if node != null:
			node.queue_free()
		return null

	var zone_node := node as Node3D
	if zone_node.has_method("configure_zone"):
		zone_node.configure_zone(zone_data, entry)
	else:
		zone_node.name = _safe_node_name(str(zone_data.get("id", zone_type)))
	created_zone_count += 1
	return zone_node


func registered_zone_type_count() -> int:
	return catalog.registered_zone_type_count() if catalog != null else 0


func catalog_loaded() -> bool:
	return catalog != null and registered_zone_type_count() > 0


func _safe_node_name(value: String) -> String:
	return value.replace(".", "_").replace("/", "_").replace(":", "_")
