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
@export var road_setback_m := 5.0
@export var building_spacing_m := 4.0
@export var boundary_setback_m := 2.5
@export var grid_jitter_m := 1.5

@export_group("Height hints")
@export var min_floors := 1
@export var max_floors := 8
@export var floor_height_m := 3.2

@export_group("Asset normalization")
@export var nominal_asset_footprint_m2 := 100.0
@export var min_asset_scale_multiplier := 0.75
@export var max_asset_scale_multiplier := 1.45


func average_building_footprint_m2() -> float:
	return max(1.0, (min_building_footprint_m2 + max_building_footprint_m2) * 0.5)


func clamp_building_count(value: int) -> int:
	var lower := max(0, min_buildings)
	var upper := max(lower, max_buildings)
	return clampi(value, lower, upper)


func random_footprint_m2(rng: RandomNumberGenerator) -> float:
	var lower := max(1.0, min_building_footprint_m2)
	var upper := max(lower, max_building_footprint_m2)
	return rng.randf_range(lower, upper)


func random_floor_count(rng: RandomNumberGenerator) -> int:
	var lower := max(1, min_floors)
	var upper := max(lower, max_floors)
	return rng.randi_range(lower, upper)
