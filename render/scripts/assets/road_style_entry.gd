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
@export var description := ""
