extends SceneTree


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var options := _parse_user_args()
	var scene_path := String(options.get("scene", "res://scenes/authoring/DistrictAuthoringMap.tscn"))
	var out_path := String(options.get("out", ""))
	if out_path.is_empty():
		push_error("--out is required")
		quit(2)
		return

	var packed: Variant = load(scene_path)
	if not (packed is PackedScene):
		push_error("Authoring scene not found or not a PackedScene: %s" % scene_path)
		quit(3)
		return

	var map_root := (packed as PackedScene).instantiate()
	root.add_child(map_root)

	var spec := _build_spec(map_root, options)
	var error := DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	if error != OK:
		push_error("Cannot create output directory %s: %s" % [out_path.get_base_dir(), error])
		quit(4)
		return

	var file := FileAccess.open(out_path, FileAccess.WRITE)
	if file == null:
		push_error("Cannot write district spec: %s" % out_path)
		quit(5)
		return
	file.store_string(JSON.stringify(spec, "\t") + "\n")
	file.close()
	print("[OK] Exported Godot authoring scene to %s" % out_path)
	quit(0)


func _build_spec(map_root: Node, options: Dictionary) -> Dictionary:
	var traffic_light_rows := _collect_marker_rows(map_root, "authoring_traffic_light", {})
	var traffic_light_ids := _id_set_from_rows(traffic_light_rows, "intersection_id")
	var intersections := _intersection_dict(
		_collect_marker_rows(map_root, "authoring_intersection", {"traffic_light_ids": traffic_light_ids})
	)
	var roads := _collect_marker_rows(map_root, "authoring_road", {"intersections": intersections})
	var zones := _collect_marker_rows(map_root, "authoring_zone", {})
	var flows := _collect_marker_rows(map_root, "authoring_spawn", {})
	var flow_ids := _flow_ids(flows)
	var candidates := _collect_marker_rows(
		map_root,
		"authoring_investment_candidate",
		{"flow_ids": flow_ids}
	)
	return {
		"metadata": _metadata(map_root, options),
		"zones": zones,
		"intersections": intersections.values(),
		"roads": roads,
		"vehicle_types": _default_vehicle_types(),
		"flows": flows,
		"scenarios": _default_scenarios(flow_ids),
		"controllers": _default_controllers(),
		"investment_candidates": candidates,
		"finance_assumptions": _default_finance_assumptions(),
	}


func _metadata(map_root: Node, options: Dictionary) -> Dictionary:
	if map_root.has_method("authoring_metadata"):
		return map_root.call("authoring_metadata", options)
	return {
		"id": String(options.get("district_id", "godot_authoring_district_v1")),
		"name": String(options.get("district_name", "Godot Authored District V1")),
		"version": String(options.get("version", "0.1.0")),
		"horizon_seconds": int(options.get("horizon_seconds", "3600")),
		"time_step_seconds": int(options.get("time_step_seconds", "1")),
	}


func _collect_marker_rows(map_root: Node, group_name: String, context: Dictionary) -> Array:
	var output := []
	for node in _nodes_in_group(map_root, group_name):
		if not node.has_method("to_authoring_rows"):
			push_error("%s belongs to %s but does not implement to_authoring_rows()" % [node.get_path(), group_name])
			continue
		var rows: Variant = node.call("to_authoring_rows", context)
		if not (rows is Array):
			push_error("%s.to_authoring_rows() must return Array" % node.get_path())
			continue
		for row in rows:
			if row is Dictionary and not (row as Dictionary).is_empty():
				output.append(row)
	return output


func _intersection_dict(rows: Array) -> Dictionary:
	var output := {}
	for row in rows:
		var row_dict := row as Dictionary
		var intersection_id := String(row_dict.get("id", ""))
		if intersection_id.is_empty():
			push_error("Intersection marker returned empty id.")
			continue
		output[intersection_id] = row_dict
	return output


func _id_set_from_rows(rows: Array, id_field: String) -> Dictionary:
	var output := {}
	for row in rows:
		if not (row is Dictionary):
			continue
		var value := String((row as Dictionary).get(id_field, ""))
		if not value.is_empty():
			output[value] = true
	return output


func _default_vehicle_types() -> Array:
	return [
		{"id": "CAR", "passenger_count": 1.4, "pcu": 1.0, "value_class": "commuter"},
		{"id": "MOTORBIKE", "passenger_count": 1.1, "pcu": 0.35, "value_class": "commuter"},
		{"id": "DELIVERY_BIKE", "passenger_count": 1.0, "pcu": 0.35, "value_class": "commerce"},
		{"id": "BUS", "passenger_count": 32.0, "pcu": 2.5, "value_class": "public_transport"},
		{"id": "SCHOOL_BUS", "passenger_count": 24.0, "pcu": 2.2, "value_class": "school"},
		{"id": "WORKER_SHUTTLE", "passenger_count": 18.0, "pcu": 2.0, "value_class": "worker"},
		{"id": "AMBULANCE", "passenger_count": 2.0, "pcu": 1.3, "value_class": "emergency", "priority_level": 10},
		{"id": "LIGHT_TRUCK", "passenger_count": 1.0, "pcu": 1.5, "value_class": "logistics"},
		{"id": "HEAVY_TRUCK", "passenger_count": 1.0, "pcu": 2.8, "value_class": "logistics"},
	]


func _default_scenarios(flow_ids: Array[String]) -> Array:
	return [
		{"id": "normal_weekday", "name": "Ngày thường", "description": "Baseline demand from Godot authoring scene.", "flow_multipliers": {}},
		{"id": "school_rush", "name": "Cao điểm trường học", "description": "School commute stress.", "flow_multipliers": _filtered_multipliers(flow_ids, {"F_RES_SCHOOL": 1.6})},
		{"id": "industrial_shift", "name": "Đổi ca công nghiệp", "description": "Industrial worker and logistics demand spike.", "flow_multipliers": _filtered_multipliers(flow_ids, {"F_RES_INDUSTRY": 1.5, "F_LOGISTICS": 1.3})},
		{"id": "hospital_emergency", "name": "Ưu tiên cấp cứu", "description": "Emergency access stress test.", "flow_multipliers": _filtered_multipliers(flow_ids, {"F_MEDICAL_EMERGENCY": 3.0})},
		{"id": "nightlife_peak", "name": "Giờ tan khu giải trí", "description": "Late evening nightlife demand.", "flow_multipliers": _filtered_multipliers(flow_ids, {"F_NIGHTLIFE_OUT": 1.8})},
	]


func _default_controllers() -> Array:
	return [
		{"id": "fixed_time", "name": "Fixed-time baseline", "type": "baseline"},
		{"id": "rule_based", "name": "Rule-based SUMO baseline", "type": "baseline"},
		{"id": "rl_policy", "name": "RL placeholder", "type": "rl_placeholder"},
	]


func _default_finance_assumptions() -> Dictionary:
	return {
		"value_of_time_vnd_per_hour": 45000.0,
		"bus_passenger_value_multiplier": 1.2,
		"emergency_delay_value_vnd_per_hour": 300000.0,
		"logistics_delay_value_vnd_per_truck_hour": 120000.0,
		"fuel_emission_saving_vnd_per_delay_hour": 15000.0,
		"deployment_risk_penalty_vnd": 50000000.0,
		"status": {
			"value_of_time": "placeholder",
			"emergency_delay": "placeholder",
			"logistics_delay": "placeholder",
		},
	}


func _filtered_multipliers(flow_ids: Array[String], candidates: Dictionary) -> Dictionary:
	var output := {}
	for flow_id in candidates.keys():
		if flow_ids.has(String(flow_id)):
			output[String(flow_id)] = float(candidates[flow_id])
	return output


func _flow_ids(flows: Array) -> Array[String]:
	var output: Array[String] = []
	for flow in flows:
		output.append(String((flow as Dictionary)["id"]))
	return output


func _nodes_in_group(root_node: Node, group_name: String) -> Array[Node]:
	var output: Array[Node] = []
	_collect_nodes(root_node, group_name, output)
	return output


func _collect_nodes(node: Node, group_name: String, output: Array[Node]) -> void:
	if node.is_in_group(group_name):
		output.append(node)
	for child in node.get_children():
		_collect_nodes(child, group_name, output)


func _parse_user_args() -> Dictionary:
	var parsed := {}
	var args := OS.get_cmdline_user_args()
	var index := 0
	while index < args.size():
		var arg := String(args[index])
		if arg in ["--scene", "--out", "--district-id", "--district-name", "--version", "--horizon-seconds", "--time-step-seconds"] and index + 1 < args.size():
			var key := arg.trim_prefix("--").replace("-", "_")
			parsed[key] = String(args[index + 1])
			index += 2
		else:
			index += 1
	return parsed
