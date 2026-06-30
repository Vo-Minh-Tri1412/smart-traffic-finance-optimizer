class_name TracePlaybackClock
extends RefCounted

var start_time_seconds := 0.0
var end_time_seconds := 0.0
var current_time_seconds := 0.0
var playback_speed := 1.0
var loop := true
var is_playing := false


func configure(start_time: float, end_time: float, speed: float = 1.0, should_loop: bool = true) -> void:
	start_time_seconds = start_time
	end_time_seconds = max(start_time, end_time)
	current_time_seconds = start_time_seconds
	playback_speed = max(0.0, speed)
	loop = should_loop
	is_playing = false


func play() -> void:
	is_playing = true


func pause() -> void:
	is_playing = false


func restart() -> void:
	current_time_seconds = start_time_seconds


func seek(time_seconds: float) -> void:
	current_time_seconds = clamp(time_seconds, start_time_seconds, end_time_seconds)


func advance(delta_seconds: float) -> float:
	if not is_playing:
		return current_time_seconds
	current_time_seconds += max(0.0, delta_seconds) * playback_speed
	if current_time_seconds > end_time_seconds:
		if loop and end_time_seconds > start_time_seconds:
			var duration := end_time_seconds - start_time_seconds
			current_time_seconds = start_time_seconds + fmod(current_time_seconds - start_time_seconds, duration)
		else:
			current_time_seconds = end_time_seconds
			is_playing = false
	return current_time_seconds


func duration_seconds() -> float:
	return end_time_seconds - start_time_seconds
