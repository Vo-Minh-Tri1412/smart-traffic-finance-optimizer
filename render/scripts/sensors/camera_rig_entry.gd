class_name CameraRigEntry
extends Resource

@export var sensor_id := ""
@export var display_name := ""
@export var role := "intersection"
@export var enabled := true
@export var split := "train"
@export var position := Vector3.ZERO
@export var rotation_degrees := Vector3(-45.0, 0.0, 0.0)
@export var fov_degrees := 60.0
@export var image_size := Vector2i(640, 640)
@export var capture_interval_seconds := 1.0
@export var target_tags: Array[String] = []
@export var notes := ""


func normalized_sensor_id() -> String:
	return sensor_id.strip_edges()


func safe_sensor_id() -> String:
	var value := normalized_sensor_id()
	if value.is_empty():
		value = "CAM_UNNAMED"
	return value.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")
