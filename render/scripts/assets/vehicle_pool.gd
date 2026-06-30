extends RefCounted

var factory = null
var pool_root: Node = null
var available_by_type: Dictionary = {}
var pooled_vehicle_type_by_node_id: Dictionary = {}
var created_count := 0
var reused_count := 0
var released_count := 0


func configure(vehicle_factory, parent_node: Node) -> void:
	factory = vehicle_factory
	pool_root = parent_node
	available_by_type.clear()
	pooled_vehicle_type_by_node_id.clear()
	created_count = 0
	reused_count = 0
	released_count = 0


func acquire(vehicle_type: String, vehicle_id: String = "") -> Node3D:
	var canonical_type := _canonical_vehicle_type(vehicle_type)
	var bucket: Array = available_by_type.get(canonical_type, [])
	var node: Node3D = null
	while not bucket.is_empty() and node == null:
		var candidate = bucket.pop_back()
		if is_instance_valid(candidate) and candidate is Node3D:
			node = candidate as Node3D
	available_by_type[canonical_type] = bucket

	if node != null:
		reused_count += 1
		if node.has_method("configure"):
			node.configure(vehicle_type, vehicle_id)
		node.visible = true
		node.process_mode = Node.PROCESS_MODE_INHERIT
		return node

	if factory == null:
		push_error("VehiclePool has no VehicleFactory configured.")
		return null

	node = factory.create_vehicle(vehicle_type, vehicle_id)
	if node == null:
		return null
	created_count += 1
	pooled_vehicle_type_by_node_id[node.get_instance_id()] = canonical_type
	return node


func release(node: Node) -> void:
	if node == null or not is_instance_valid(node):
		return
	var canonical_type := String(pooled_vehicle_type_by_node_id.get(node.get_instance_id(), "UNKNOWN"))
	if not available_by_type.has(canonical_type):
		available_by_type[canonical_type] = []
	node.visible = false
	node.process_mode = Node.PROCESS_MODE_DISABLED
	if node.get_parent() != pool_root and pool_root != null:
		if node.get_parent() != null:
			node.get_parent().remove_child(node)
		pool_root.add_child(node)
	(available_by_type[canonical_type] as Array).append(node)
	released_count += 1


func available_count() -> int:
	var total := 0
	for bucket in available_by_type.values():
		total += (bucket as Array).size()
	return total


func pool_type_count() -> int:
	return available_by_type.size()


func _canonical_vehicle_type(vehicle_type: String) -> String:
	if factory != null and factory.registry != null:
		return factory.registry.canonical_vehicle_type(vehicle_type)
	return vehicle_type.strip_edges().to_upper().replace("-", "_").replace(" ", "_")
