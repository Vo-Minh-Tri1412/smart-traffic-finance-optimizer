class_name PreviewCameraController
extends Camera3D

@export var target_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var auto_fit_on_ready := true
@export var orthographic_margin := 1.15
@export var min_orthographic_size := 80.0
@export var max_orthographic_size := 340.0
@export var preview_height := 220.0
@export var use_top_down_preview := true
@export var enable_runtime_controls := true
@export var min_zoom_size := 18.0
@export var max_zoom_size := 340.0
@export var zoom_factor := 0.82
@export var keyboard_pan_units_per_second := 95.0
@export var drag_pan_multiplier := 1.0
@export var manual_start_when_no_target := false
@export var manual_start_position := Vector3(0.0, 32.0, 30.0)
@export var manual_start_rotation_degrees := Vector3(-55.0, 0.0, 0.0)
@export var manual_start_orthographic_size := 42.0

var _fit_attempts := 0
var _is_dragging := false


func _ready() -> void:
	if manual_start_when_no_target:
		_apply_manual_start_view()
	if auto_fit_on_ready:
		call_deferred("_fit_after_scene_ready")


func _fit_after_scene_ready() -> void:
	if fit_to_world():
		return
	_fit_attempts += 1
	if _fit_attempts < 8:
		call_deferred("_fit_after_scene_ready")


func fit_to_world() -> bool:
	var world := get_node_or_null(target_world_path)
	if world == null or not world.has_method("has_geometry_bounds"):
		return false
	if not bool(world.has_geometry_bounds()):
		return false

	var bounds_min: Vector2 = world.get_geometry_bounds_min()
	var bounds_max: Vector2 = world.get_geometry_bounds_max()
	var world_scale: float = float(world.get("world_scale"))
	var width: float = abs(bounds_max.x - bounds_min.x) * world_scale
	var depth: float = abs(bounds_max.y - bounds_min.y) * world_scale
	var fitted_size: float = float(clamp(
		max(width, depth) * orthographic_margin,
		min_orthographic_size,
		max_orthographic_size
	))

	projection = Camera3D.PROJECTION_ORTHOGONAL
	size = fitted_size
	if use_top_down_preview:
		position = Vector3(0.0, preview_height, 0.0)
		rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	else:
		position = Vector3(0.0, preview_height, fitted_size * 0.65)
		rotation_degrees = Vector3(-55.0, 0.0, 0.0)
	current = true
	return true


func _unhandled_input(event: InputEvent) -> void:
	if not enable_runtime_controls:
		return
	if event is InputEventMouseButton:
		_handle_mouse_button(event as InputEventMouseButton)
	elif event is InputEventMouseMotion:
		_handle_mouse_motion(event as InputEventMouseMotion)
	elif event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and not key_event.echo and key_event.keycode == KEY_R:
			if not fit_to_world() and manual_start_when_no_target:
				_apply_manual_start_view()
			get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	if not enable_runtime_controls:
		return
	_handle_keyboard_pan(delta)


func _handle_mouse_button(event: InputEventMouseButton) -> void:
	if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
		_zoom_by_factor(zoom_factor)
		get_viewport().set_input_as_handled()
	elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
		_zoom_by_factor(1.0 / zoom_factor)
		get_viewport().set_input_as_handled()
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		_is_dragging = event.pressed
		get_viewport().set_input_as_handled()


func _handle_mouse_motion(event: InputEventMouseMotion) -> void:
	if not _is_dragging or projection != Camera3D.PROJECTION_ORTHOGONAL:
		return
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	var safe_width: float = max(1.0, viewport_size.x)
	var safe_height: float = max(1.0, viewport_size.y)
	var aspect: float = safe_width / safe_height
	var x_units_per_pixel: float = (size * aspect) / safe_width
	var z_units_per_pixel: float = size / safe_height
	position.x -= event.relative.x * x_units_per_pixel * drag_pan_multiplier
	position.z -= event.relative.y * z_units_per_pixel * drag_pan_multiplier
	get_viewport().set_input_as_handled()


func _handle_keyboard_pan(delta: float) -> void:
	var direction := Vector3.ZERO
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		direction.x -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		direction.x += 1.0
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		direction.z -= 1.0
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		direction.z += 1.0
	if direction == Vector3.ZERO:
		return
	var speed_scale: float = max(0.25, size / 160.0)
	position += direction.normalized() * keyboard_pan_units_per_second * speed_scale * delta


func _zoom_by_factor(factor: float) -> void:
	if projection != Camera3D.PROJECTION_ORTHOGONAL:
		projection = Camera3D.PROJECTION_ORTHOGONAL
	size = float(clamp(size * factor, min_zoom_size, max_zoom_size))


func _apply_manual_start_view() -> void:
	projection = Camera3D.PROJECTION_ORTHOGONAL
	size = manual_start_orthographic_size
	position = manual_start_position
	rotation_degrees = manual_start_rotation_degrees
	current = true
