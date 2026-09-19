# Unreal render adapter migration plan

## Accepted next delivery (2026-09-19)

The user selected semi-realistic interactive rendering on the existing machine, free resources,
native editable asset catalogs and a first demo corner on the unchanged map. The new
[asset pipeline design](UNREAL_ASSET_PIPELINE.md) specifies components, profiles, replacement tests,
streaming and sensor boundaries. [System delivery plan](SYSTEM_DELIVERY_PLAN.md) owns milestone
dependencies. These are planned changes; the verified scaffold below has not gained them yet.

## Boundary and authority

`render_unreal/TrafficRender.uproject` is a renderer/sensor adapter, not a game. SUMO remains
authoritative for routes, vehicle motion, queues, traffic-light phases and traffic-event effects.
Unreal consumes prepared artifacts and may render geometry, replay vehicles, calibrated camera
outputs and sensor labels; it must not recalculate traffic or finance decisions. Godot remains the
legacy reference/fallback adapter. No CatRoom assets or gameplay assumptions are used.

The adapter preserves these contracts exactly:

`geometry_manifest.v1`, `vehicle_trace.v2`, `visibility_trace.v1`, `traffic_light_trace.v1`,
`semantic_overlay.v2`, `event_trace.v1`, `render_run_manifest.v1`, `sensor_dataset_manifest.v1`,
and the shared `camera_calibration.v1` artifact.

## Implemented in this scaffold

- A UE 5.8 project with primary `TrafficRender` module and `TrafficRenderBridge` plugin containing
  `TrafficRenderRuntime` and `TrafficRenderEditor`.
- Strict JSON/JSONL schema and required-field checks for render and vehicle manifests. Unsupported
  versions fail with an actionable error; declared optional files produce warnings when absent.
- Explicit SUMO local origin and metres-to-centimetres conversion. Vehicle trace `x/y` is treated as
  `front_bumper_center`; the replay cuboid center subtracts `length_m / 2` along SUMO heading.
  Sublane `pos_lat_m` is carried as state and is not added a second time.
- Deterministic trace sampling/interpolation, playback clock, world subsystem and debug proxy actor.
  Proxy dimensions come from canonical trace dimensions rather than implicit mesh dimensions.
- SUMO `.net.xml` lane-shape ingestion into a lightweight procedural lane mesh with lane-count and
  junction-count QA counters. This is ROI-friendly and intentionally does not instantiate a full
  open-world editable city.
- `camera_calibration.v1` validation and a Blueprint-facing contract self-test API.
- Editor automation test `TrafficRender.Bridge.ContractSelfTest` and the Python artifact smoke
  script `scripts/render/unreal_contract_smoke.py`.

## Verified vs planned

Verified by source inspection and the Python smoke path: schema IDs, strict required fields, origin
and unit policy, front-bumper centering formula, deterministic interpolation algorithm, and editor
test registration. On 2026-09-17 the NetFxSDK blocker was resolved and UE 5.8.2
compiled all three adapter DLLs successfully (MSVC 14.44, Windows SDK 10.0.26100,
two parallel actions, 98.73 seconds). Native automation passed all four tests,
with zero test warnings/errors and editor exit code 0 under NullRHI.

The 2026-09-16 continuation repeated that build and confirmed the same missing SDK.
Eight Python contract tests now pass, including non-finite/coerced coordinates,
duplicate vehicle IDs and missing network rejection. Source review corrected the
native self-test's expected northbound coordinates and bounds vehicle actor lifetime
by the current visible set. Native automation includes trajectory/heading interpolation
and coordinate round-trip tests; these now pass, together with the artifact replay fixture.
The prepared-network test built the retained real SUMO network: 88,163 lanes,
236,434 mesh segments and 17,866 junction records. Its trace is a two-frame synthetic
fixture, not map-demand evidence. NullRHI does not verify visible rendering, frame
rate, sensor-image quality, or complete interactive replay. The optional check can
be reproduced using `Tests/Fixtures/retained_net_geometry/manifest.json`.
Live MCP initialize and tools/list probes returned HTTP 200 on the observed
`127.0.0.1:8001` listener (protocol 2025-11-25), and initialized returned 202.
The endpoint stopped when the test editor exited normally; no persistent client
connection or tool action is claimed. On 2026-09-18, both Net48 SDK and TargetingPack
components were confirmed by `vswhere`, with v4.8 reference assemblies present.
Reproducible build, native-test, editor-launch and project-local MCP instructions are
in `render_unreal/README.md`; `render_unreal/codex-mcp.example.toml` is an opt-in example.

Planned next steps are material/sensor integration backed by `MovieRenderPipeline`, depth/instance
visibility and `sensor_dataset_manifest.v1` export, traffic-light/semantic/event visual layers,
incremental ROI streaming and a packaged commandlet run on a machine with the UE prerequisites.
MCP is an editor-development control plane only; it is not a high-rate trace transport.

## MCP/editor setup

The project enables `ModelContextProtocol`, `ToolsetRegistry`, `EditorToolset`,
`AutomationTestToolset`, `PythonScriptPlugin`, `EditorScriptingUtilities`, `MovieRenderPipeline`,
and `ProceduralMeshComponent`. `Config/DefaultEditorPerProjectUserSettings.ini` configures MCP at
`/mcp`, port `8001`, auto-start and tool search. Keep high-rate replay offline from MCP: load a
manifest from disk and use MCP/editor tools for inspection, automation and QA reports.

For the RTX 3050 4 GB / 16 GB target, use a small active radius, batched/procedural lane geometry,
debug proxy vehicles and movie-render batches. Do not scale SUMO coordinates by `0.02`; use the
declared 100 UE centimetres per SUMO metre conversion with an explicit origin.
