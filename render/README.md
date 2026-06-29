# Godot Render Workspace

This folder contains the Godot-side workspace for the future 3D synthetic visual sensor layer.

Godot is a renderer and demo/sensor layer. It should consume exported SUMO/SUMO-RL trajectories and
render camera-like frames, videos, and YOLO labels. It must not replace SUMO-RL as the official
traffic/RL environment.

## Current status

- Godot project created with Godot 4.6.
- Godot AI MCP plugin installed under `addons/godot_ai`.
- Codex is configured through the Godot AI MCP server.
- No project renderer scene is implemented yet.

## Do not commit

Generated outputs must stay out of Git:

- `.godot/`
- `generated/`
- `exports/`
- `screenshots/`
- `datasets/`
- `videos/`
- `captures/`

Put generated frames, labels, videos, model outputs, and render logs in the Google Drive Data Hub.
