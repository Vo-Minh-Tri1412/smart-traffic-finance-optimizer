class_name RoadStyleEntry
extends Resource

@export var road_role := "default"
@export var road_root_scene: PackedScene
@export var lane_visual_scene: PackedScene
@export var lane_material: Material
@export var lane_marking_material: Material
@export var junction_material: Material
@export var lane_color := Color(0.07, 0.072, 0.075)
@export var junction_color := Color(0.035, 0.036, 0.04)
@export var width_multiplier := 2.4
@export var min_visual_lane_width := 0.14
@export var show_markings := true
@export_group("Roadside Assets")
@export var show_roadside_props := true
@export var roadside_prop_scenes: Array[PackedScene] = []
@export var roadside_prop_spacing_m := 120.0
@export var roadside_prop_offset_m := 5.2
@export var roadside_prop_scale := 0.035
@export var roadside_prop_lane_stride := 8
@export var max_roadside_props_per_lane := 1
@export var description := ""
