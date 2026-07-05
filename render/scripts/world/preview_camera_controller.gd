class_name PreviewCameraController
extends Camera3D

@export var target_world_path: NodePath = NodePath("../DistrictReplayWorld")
@export var auto_fit_on_ready := true
@export var orthographic_margin := 1.15
@export var min_orthographic_size := 32.0
@export var max_orthographic_size := 340.0
@export var preview_height := 220.0
@export var use_top_down_preview := true
@export var enable_runtime_controls := true
@export var min_zoom_size := 8.0
@export var max_zoom_size := 340.0
@export var zoom_factor := 0.82
@export var keyboard_pan_units_per_second := 95.0
@export var drag_pan_multiplier := 1.0
@export var manual_start_when_no_target := false
@export var use_fly_preview := true
@export var manual_start_position := Vector3(0.0, 85.0, 145.0)
@export var manual_start_rotation_degrees := Vector3(-28.0, 0.0, 0.0)
@export var manual_start_orthographic_size := 42.0
@export var fly_speed_units_per_second := 85.0
@export var fly_fast_multiplier := 4.0
@export var mouse_look_sensitivity := 0.12
@export var mouse_wheel_dolly_units := 55.0
@export var fly_min_height := 2.0
@export var fly_max_height := 1400.0
@export var horizontal_fly_movement := true

var _fit_attempts := 0
var _is_dragging := false


func _ready() -> void:
	if use_fly_preview:
		_apply_manual_start_view()
		return
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
		if key_event.pressed and not key_event.echo:
			if key_event.keycode == KEY_R:
				_apply_manual_start_view()
				get_viewport().set_input_as_handled()
			elif key_event.keycode == KEY_F:
				if use_fly_preview:
					_frame_world_fly()
				else:
					fit_to_world()
			get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	if not enable_runtime_controls:
		return
	_handle_keyboard_pan(delta)


func _handle_mouse_button(event: InputEventMouseButton) -> void:
	if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
		if use_fly_preview:
			_dolly_fly_camera(1.0)
		else:
			_zoom_by_factor(zoom_factor)
		get_viewport().set_input_as_handled()
	elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
		if use_fly_preview:
			_dolly_fly_camera(-1.0)
		else:
			_zoom_by_factor(1.0 / zoom_factor)
		get_viewport().set_input_as_handled()
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		_is_dragging = event.pressed
		get_viewport().set_input_as_handled()


func _handle_mouse_motion(event: InputEventMouseMotion) -> void:
	if use_fly_preview and _is_dragging:
		rotation_degrees.y -= event.relative.x * mouse_look_sensitivity
		rotation_degrees.x = clamp(rotation_degrees.x - event.relative.y * mouse_look_sensitivity, -86.0, 35.0)
		get_viewport().set_input_as_handled()
		return
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
	if use_fly_preview:
		_handle_fly_keyboard(delta)
		return
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


func _handle_fly_keyboard(delta: float) -> void:
	var direction := Vector3.ZERO
	var right := global_transform.basis.x
	var forward := -global_transform.basis.z
	if horizontal_fly_movement:
		right.y = 0.0
		forward.y = 0.0
		right = right.normalized() if right.length_squared() > 0.0001 else Vector3.RIGHT
		forward = forward.normalized() if forward.length_squared() > 0.0001 else Vector3.FORWARD
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		direction -= right
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		direction += right
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		direction += forward
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		direction -= forward
	if Input.is_key_pressed(KEY_E) or Input.is_key_pressed(KEY_SPACE):
		direction += Vector3.UP
	if Input.is_key_pressed(KEY_Q) or Input.is_key_pressed(KEY_CTRL):
		direction -= Vector3.UP
	if direction == Vector3.ZERO:
		return
	var speed := fly_speed_units_per_second
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= fly_fast_multiplier
	position += direction.normalized() * speed * delta
	_clamp_fly_height()


func _zoom_by_factor(factor: float) -> void:
	if use_fly_preview:
		_dolly_fly_camera(1.0 if factor < 1.0 else -1.0)
		return
	if projection != Camera3D.PROJECTION_ORTHOGONAL:
		projection = Camera3D.PROJECTION_ORTHOGONAL
	size = float(clamp(size * factor, min_zoom_size, max_zoom_size))


func _dolly_fly_camera(direction: float) -> void:
	var forward := -global_transform.basis.z
	if forward.length_squared() <= 0.0001:
		return
	position += forward.normalized() * mouse_wheel_dolly_units * direction
	_clamp_fly_height()


func _clamp_fly_height() -> void:
	position.y = clamp(position.y, fly_min_height, fly_max_height)


func _frame_world_fly() -> bool:
	var world := get_node_or_null(target_world_path)
	if world == null or not world.has_method("has_geometry_bounds"):
		return false
	if not bool(world.has_geometry_bounds()):
		return false
	var bounds_min: Vector2 = world.get_geometry_bounds_min()
	var bounds_max: Vector2 = world.get_geometry_bounds_max()
	var world_scale: float = float(world.get("world_scale"))
	var center := (bounds_min + bounds_max) * 0.5
	var width: float = abs(bounds_max.x - bounds_min.x) * world_scale
	var depth: float = abs(bounds_max.y - bounds_min.y) * world_scale
	var span: float = max(width, depth)
	position = Vector3(0.0, clamp(span * 0.18, 80.0, fly_max_height), clamp(span * 0.32, 180.0, 900.0))
	if world.has_method("world_position_for_sumo_coordinates"):
		var point = world.world_position_for_sumo_coordinates([[center.x, center.y]], 0.0)
		if point is Array and not (point as Array).is_empty() and (point as Array)[0] is Vector3:
			var center_world := (point as Array)[0] as Vector3
			position.x = center_world.x
			position.z = center_world.z + clamp(span * 0.32, 180.0, 900.0)
	rotation_degrees = Vector3(-42.0, 0.0, 0.0)
	current = true
	return true


func _apply_manual_start_view() -> void:
	if use_fly_preview:
		projection = Camera3D.PROJECTION_PERSPECTIVE
	else:
		projection = Camera3D.PROJECTION_ORTHOGONAL
		size = manual_start_orthographic_size
	position = manual_start_position
	rotation_degrees = manual_start_rotation_degrees
	_clamp_fly_height()
	current = true
