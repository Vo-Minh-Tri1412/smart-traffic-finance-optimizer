class_name ZoneAssetEntry
extends Resource

@export var zone_type := ""
@export var zone_scene: PackedScene
@export var ground_material: Material
@export var building_scenes: Array = []
@export var building_scene_paths: PackedStringArray = []
@export var building_density := 4
@export var min_building_scale := 0.8
@export var max_building_scale := 1.35
@export var building_asset_scale := 0.05
@export var seed := 17
@export var label_prefix := ""
@export var description := ""
