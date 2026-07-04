class_name TrafficLightAssetEntry
extends Resource

@export var role := "default"
@export var visual_scene: PackedScene
@export var pole_asset_scene: PackedScene
@export var head_asset_scene: PackedScene
@export var visual_scale := 1.0
@export var asset_scale := 0.04
@export var pole_height := 1.8
@export var lamp_radius := 0.12
@export var red_material: Material
@export var yellow_material: Material
@export var green_material: Material
@export var inactive_material: Material
@export var description := ""
