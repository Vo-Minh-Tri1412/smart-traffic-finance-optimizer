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
	var traffic_light_ids := _traffic_light_ids(map_root)
	var intersections := _collect_intersections(map_root, traffic_light_ids)
	var roads := _collect_roads(map_root, intersections)
	var zones := _collect_zones(map_root)
	var flows := _collect_flows(map_root)
	var flow_ids := _flow_ids(flows)
	return {
		"metadata": {
			"id": String(options.get("district_id", "godot_authoring_district_v1")),
			"name": String(options.get("district_name", "Godot Authored District V1")),
			"version": String(options.get("version", "0.1.0")),
			"horizon_seconds": int(options.get("horizon_seconds", "3600")),
			"time_step_seconds": int(options.get("time_step_seconds", "1")),
		},
		"zones": zones,
		"intersections": intersections.values(),
		"roads": roads,
		"vehicle_types": _default_vehicle_types(),
		"flows": flows,
		"scenarios": _default_scenarios(flow_ids),
		"controllers": _default_controllers(),
		"investment_candidates": _collect_investment_candidates(map_root, flow_ids),
		"finance_assumptions": _default_finance_assumptions(),
	}


func _collect_intersections(map_root: Node, traffic_light_ids: Dictionary) -> Dictionary:
	var output := {}
	for node in _nodes_in_group(map_root, "authoring_intersection"):
		var intersection_id := String(node.get("intersection_id"))
		if intersection_id.is_empty():
			push_error("%s: intersection_id is required" % node.get_path())
			continue
		var display_name := String(node.get("display_name"))
		if display_name.is_empty():
			display_name = intersection_id
		var global := (node as Node3D).global_position
		output[intersection_id] = {
			"id": intersection_id,
			"name": display_name,
			"x": _round3(global.x / 1000.0),
			"y": _round3(global.z / 1000.0),
			"tags": _string_array(node.get("tags")),
			"signalized": bool(node.get("signalized")) or traffic_light_ids.has(intersection_id),
		}
	return output


func _collect_roads(map_root: Node, intersections: Dictionary) -> Array:
	var output := []
	for node in _nodes_in_group(map_root, "authoring_road"):
		var road_id := String(node.get("road_id"))
		var from_id := String(node.get("from_intersection"))
		var to_id := String(node.get("to_intersection"))
		if road_id.is_empty() or from_id.is_empty() or to_id.is_empty():
			push_error("%s: road_id/from_intersection/to_intersection are required" % node.get_path())
			continue
		if not intersections.has(from_id) or not intersections.has(to_id):
			push_error("%s: road endpoint not found: %s -> %s" % [road_id, from_id, to_id])
			continue
		var length_km := _road_length_km(node, intersections[from_id], intersections[to_id])
		var row := _road_row(node, road_id, from_id, to_id, length_km)
		output.append(row)
		if bool(node.get("bidirectional")):
			output.append(_road_row(node, "%s_REV" % road_id, to_id, from_id, length_km))
	return output


func _road_row(node: Node, road_id: String, from_id: String, to_id: String, length_km: float) -> Dictionary:
	return {
		"id": road_id,
		"from": from_id,
		"to": to_id,
		"length_km": length_km,
		"speed_kph": float(node.get("speed_kph")),
		"lanes": int(node.get("lanes")),
		"capacity": float(node.get("capacity")),
		"tags": _string_array(node.get("tags")),
		"truck_allowed": bool(node.get("truck_allowed")),
	}


func _road_length_km(node: Node, from_row: Dictionary, to_row: Dictionary) -> float:
	var override := float(node.get("length_km_override"))
	if override > 0.0:
		return _round3(override)
	var from_point := Vector3(float(from_row["x"]) * 1000.0, 0.0, float(from_row["y"]) * 1000.0)
	var to_point := Vector3(float(to_row["x"]) * 1000.0, 0.0, float(to_row["y"]) * 1000.0)
	var points: Array[Vector3] = [from_point]
	for point in PackedVector3Array(node.get("shape_points")):
		points.append(point)
	points.append(to_point)
	var meters := 0.0
	for index in range(points.size() - 1):
		meters += points[index].distance_to(points[index + 1])
	return max(0.001, _round3(meters / 1000.0))


func _collect_zones(map_root: Node) -> Array:
	var output := []
	for node in _nodes_in_group(map_root, "authoring_zone"):
		var zone_id := String(node.get("zone_id"))
		if zone_id.is_empty():
			push_error("%s: zone_id is required" % node.get_path())
			continue
		var display_name := String(node.get("display_name"))
		if display_name.is_empty():
			display_name = zone_id
		output.append({
			"id": zone_id,
			"name": display_name,
			"type": String(node.get("zone_type")),
			"intersection_ids": _string_array(node.get("intersection_ids")),
			"economic_role": String(node.get("economic_role")),
			"peak_windows": _string_array(node.get("peak_windows")),
		})
	return output


func _collect_flows(map_root: Node) -> Array:
	var output := []
	for node in _nodes_in_group(map_root, "authoring_spawn"):
		var flow_id := String(node.get("flow_id"))
		if flow_id.is_empty():
			flow_id = String(node.get("spawn_id"))
		if flow_id.is_empty():
			push_error("%s: flow_id or spawn_id is required" % node.get_path())
			continue
		output.append({
			"id": flow_id,
			"origin_zone": String(node.get("origin_zone")),
			"destination_zone": String(node.get("destination_zone")),
			"trip_purpose": String(node.get("trip_purpose")),
			"departure_start": int(node.get("departure_start")),
			"departure_end": int(node.get("departure_end")),
			"base_volume": int(node.get("base_volume")),
			"vehicle_mix": _normalized_mix(node.get("vehicle_mix")),
			"route_policy": String(node.get("route_policy")),
		})
	return output


func _collect_investment_candidates(map_root: Node, flow_ids: Array[String]) -> Array:
	var output := []
	for node in _nodes_in_group(map_root, "authoring_investment_candidate"):
		var candidate_id := String(node.get("candidate_id"))
		if candidate_id.is_empty():
			continue
		var affected := []
		for flow_id in _string_array(node.get("affected_flow_ids")):
			if flow_ids.has(flow_id):
				affected.append(flow_id)
		output.append({
			"id": candidate_id,
			"intersection_id": String(node.get("intersection_id")),
			"upgrade_type": String(node.get("upgrade_type")),
			"capex_vnd": float(node.get("capex_vnd")),
			"annual_maintenance_vnd": float(node.get("annual_maintenance_vnd")),
			"affected_flow_ids": affected,
			"caveat": String(node.get("caveat")),
		})
	return output


func _traffic_light_ids(map_root: Node) -> Dictionary:
	var ids := {}
	for node in _nodes_in_group(map_root, "authoring_traffic_light"):
		var intersection_id := String(node.get("intersection_id"))
		if not intersection_id.is_empty():
			ids[intersection_id] = true
	return ids


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
		output.append(String(flow["id"]))
	return output


func _normalized_mix(raw: Variant) -> Dictionary:
	var values := {}
	if raw is Dictionary:
		for key in (raw as Dictionary).keys():
			var value := float((raw as Dictionary)[key])
			if value > 0.0:
				values[String(key)] = value
	if values.is_empty():
		values["MOTORBIKE"] = 0.6
		values["CAR"] = 0.4
	var total := 0.0
	for value in values.values():
		total += float(value)
	var output := {}
	for key in values.keys():
		output[String(key)] = _round3(float(values[key]) / total)
	var correction := 1.0 - _sum_values(output)
	var first_key := String(output.keys()[0])
	output[first_key] = _round3(float(output[first_key]) + correction)
	return output


func _sum_values(values: Dictionary) -> float:
	var total := 0.0
	for value in values.values():
		total += float(value)
	return total


func _string_array(raw: Variant) -> Array:
	var output := []
	if raw is Array:
		for item in raw:
			output.append(String(item))
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


func _round3(value: float) -> float:
	return snappedf(value, 0.001)


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
