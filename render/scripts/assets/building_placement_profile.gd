@tool
class_name BuildingPlacementProfile
extends Resource

@export var profile_name := ""
@export_multiline var description := ""

@export_group("Footprint and density")
@export var min_building_footprint_m2 := 60.0
@export var max_building_footprint_m2 := 180.0
@export_range(0.0, 0.9, 0.01) var target_coverage_ratio := 0.28
@export var min_buildings := 0
@export var max_buildings := 80

@export_group("Urban spacing")
@export_enum("grid_jittered", "organic_random", "campus_cluster", "yard_cluster")
var placement_pattern := "grid_jittered"
@export var road_setback_m := 5.0
@export var building_spacing_m := 4.0
@export var boundary_setback_m := 2.5
@export var grid_jitter_m := 1.5
@export_range(0.0, 1.0, 0.01) var min_fill_ratio := 0.72

@export_group("Height hints")
@export var min_floors := 1
@export var max_floors := 8
@export var floor_height_m := 3.2

@export_group("Asset normalization")
@export var nominal_asset_footprint_m2 := 100.0
@export var min_asset_scale_multiplier := 0.75
@export var max_asset_scale_multiplier := 1.45

@export_group("Orientation")
@export_enum("aligned_to_zone", "perpendicular_mix", "random")
var rotation_strategy := "perpendicular_mix"
@export_range(0.0, 45.0, 0.5) var rotation_jitter_degrees := 4.0
@export_range(0.0, 1.0, 0.01) var perpendicular_rotation_probability := 0.35


func average_building_footprint_m2() -> float:
	return max(1.0, (min_building_footprint_m2 + max_building_footprint_m2) * 0.5)


func clamp_building_count(value: int) -> int:
	var lower: int = max(0, min_buildings)
	var upper: int = max(lower, max_buildings)
	return clampi(value, lower, upper)


func random_footprint_m2(rng: RandomNumberGenerator) -> float:
	var lower: float = max(1.0, min_building_footprint_m2)
	var upper: float = max(lower, max_building_footprint_m2)
	return rng.randf_range(lower, upper)


func random_floor_count(rng: RandomNumberGenerator) -> int:
	var lower: int = max(1, min_floors)
	var upper: int = max(lower, max_floors)
	return rng.randi_range(lower, upper)
