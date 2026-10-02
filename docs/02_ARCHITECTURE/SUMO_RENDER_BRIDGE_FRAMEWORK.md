# SUMO-backed render bridge framework

SUMO/SUMO-RL owns traffic. Unreal is the sole active renderer; no alternate renderer runtime is
maintained in this checkout. The bridge remains renderer-neutral and uses versioned artifacts.

## Authority and flow

SUMO net + demand + controller → simulation → geometry/vehicle/TLS/event artifacts →
Unreal replay and optional sensor export. Economics consumes simulation outcomes, not rendered pixels.
Semantic overlays own zone/facility meaning, never a replacement road network.

| Layer | Owns | Must not own |
|---|---|---|
| SUMO | Routes, motion, queues, TLS and event effects | Art assets and finance choices |
| Python bridge | Run preparation, parsing, schema validation, manifests | Hand-placed visual geometry |
| Data/Economics | OD evidence, valuations, intervention effects | Renderer traffic physics |
| Unreal | Assets, replay, camera and planned sensor exports | Traffic or finance decisions |

Use prepared real-map artifacts; toy fixtures are only validation inputs. Never redraw the road
network just to make a screenshot. A visual window is not a change to the simulation domain.

## Implementation and extension points

Audit 2026-09-20: lane mesh hiện XY, chưa giữ road Z; vehicle elevation là contract riêng.
Native counts bao gồm internal records, khác Python external-network index.
Build/native tests gần nhất được ghi nhận 2026-09-17, chưa rerun trong audit.

Current UE module: TrafficRenderRuntime, with geometry/manifest loaders, coordinate conversion,
playback clock, replay subsystem/controller, canonical cuboid vehicles and lane mesh ingestion.
TrafficRenderEditor provides native automation tests. RGB parity, detailed assets, TLS/semantic
visual layers, physical sensor export and bounded streaming remain implementation work.

Next providers: geometry, vehicle trace, TLS state, semantic overlay, events, asset catalog,
road styles and sensor export. UE-native Data Assets configure visual resources; shared artifacts
remain JSON/XML/JSONL. See [asset pipeline](UNREAL_ASSET_PIPELINE.md) and
[native build/run](../../render_unreal/README.md).

## Contract boundary

Use geometry_manifest.v1, vehicle_trace.v2, traffic_light_trace.v1, semantic_overlay.v2,
event_trace.v1, camera_calibration.v1, visibility_trace.v1, render_run_manifest.v1 and
sensor_dataset_manifest.v1. [Contract definitions](RENDER_BRIDGE_CONTRACTS.md) own their semantics.
The Python geometry visibility producer is separate from a future UE RGB/depth/instance pass.
An unsupported schema fails explicitly; optional declared-but-missing artifacts produce warnings.

## Quality evidence

Report loaded/rendered lanes and junctions, frame counts, spawned/fallback/dropped vehicles,
zone fallback counts, off-lane distances, TLS sync, schema warnings and measured runtime performance.
Do not infer correctness from a screenshot or NullRHI test alone. Dataset exports additionally need
camera/time/instance alignment and visibility evidence. Assets must not alter physical proxy size.

Use tile geometry, pooling and camera-local loading rather than one editable actor per map element.
Sensor completeness is independent of presentation LOD. Events affect traffic only in SUMO.
MCP is optional editor tooling, not a trace transport. The [delivery plan](SYSTEM_DELIVERY_PLAN.md)
defines the accepted order, research gates and demonstration scope.
