class_name VehicleAssetEntry
extends Resource

@export var vehicle_type := ""
@export var vehicle_scene: PackedScene
@export var visual_asset_scene: PackedScene
@export var description := ""
@export var visual_scale := Vector3.ONE
@export var visual_asset_scale := Vector3.ONE
@export var visual_asset_offset := Vector3.ZERO
@export var visual_asset_rotation_degrees := Vector3.ZERO
@export var hide_base_body_when_visual_asset_exists := true
