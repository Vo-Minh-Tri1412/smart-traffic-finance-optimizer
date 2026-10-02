# SUMO Unreal adapter

## Live SUMO connection

From the repository root, run:

```powershell
uv run python scripts/render/run_sumo_unreal.py
```

The launcher builds the existing native plugin when its sources change, prepares
seven small materials once, and opens an Unreal game window. SUMO runs the retained
District 7 network with the existing random routes. A loopback TCP bridge sends
the current vehicle poses and all traffic-light states after every 0.1-second
TraCI step. Unreal builds the full road geometry from the same net and acknowledges
readiness before the simulation starts. Traffic is computed entirely by SUMO.

The camera follows the first active vehicle. Press **F** to toggle following,
use **WASD / Q / E** to move the camera, and hold the right mouse button to look.
The default run lasts 300 simulation seconds, at real-time speed. Its game window
stays open when the run finishes. Close it to stop an active run.

Use `--routes <file.rou.xml>` for another route input on this network,
`--duration 120` to change the run length, or `--speed 2` to advance twice as fast.
The existing routes test integration; they are not calibrated urban demand.
The renderer separates canonical SUMO physical proxies from replaceable visual meshes.
Vehicle models keep their proportions, fit inside the physical envelope and touch its ground plane.
Signal heads are attached to SUMO-controlled lane ends. Native Data Assets select Kenney vehicle
parts/materials, signal meshes/materials, placement, camera and lighting; Blueprint
subclasses provide presentation hooks. Asset detail can be added independently of the bridge.
No RL, QUBO, demand-generation or semantic-building gate is required by this launcher.

For verification with two GPU captures and automatic window closure:

```powershell
uv run python scripts/render/run_sumo_unreal.py --duration 120 --speed 2 --record-seconds 12 --verify
```

Each run writes a fresh directory under `artifacts/unreal_live/`: the frozen geometry
manifest, streamed frames, SUMO/Unreal logs, and producer/consumer reports.
Verification checks matching run IDs, every transmitted frame, SUMO time, actual
vehicle pose changes, signal changes, road/signal counts, screenshot files, and
the rendered vehicle centre against the canonical SUMO front-bumper conversion.

### Edit in Unreal Editor

Open TrafficRender.uproject and browse Content > LiveTraffic:

- Profiles/LiveAssets: vehicle mesh parts, material override, explicit forward axis,
  Blueprint actor class, road/ground materials and pole/housing/lens meshes and materials.
  PreserveAspectRatio defaults to true; the SUMO physical envelope remains separate.
- Profiles/LivePlacement: signal height, roadside clearance, head spacing and dimensions,
  housing offsets and ground placement. These settings do not alter SUMO lanes or traffic.
- Profiles/LiveScene: catalog/placement references, camera FOV/offsets, lighting and exposure.
- Blueprints/BP_LiveVehicle: OnSimulationStateApplied for visual animation.
- Blueprints/BP_LiveController: SceneProfile selection and OnLiveFrameApplied for presentation.

Save the assets, then restart the launcher to load the changes. No C++ edit or rebuild is
required. Select another scene with --visual-profile /Game/YourFolder/YourScene.
The bootstrap creates missing initial assets and preserves existing artist settings.
Every run exports visual_snapshot.json from the native Data Assets; it is an audit snapshot,
not a second configuration source. Critical unresolved assets stop the run explicitly.

--record-seconds uses ffmpeg to save the actual game viewport as live_simulation.mp4.
Capture intervals can vary with GPU readback; the MP4 preserves screenshot timing rather than
assuming the requested 10 Hz cadence was achieved. --speed is a target; actual wall time is
recorded in the producer report. The longer verification run observes existing SUMO phase
changes without overriding their timing. This is an UnrealEditor-hosted game viewport, not a
packaged executable or a calibrated demand model.

This UE 5.8 project consumes the repository's SUMO render contracts. Traffic motion
and decisions remain owned by SUMO. The current implementation provides lane mesh
ingestion, canonical vehicle replay and live vehicle/TLS rendering configured by native profiles.
Sensor-image export and a complete visual semantic/city layer remain separate work.

## Audit 2026-09-20

Native build/tests chưa chạy lại trong audit này; các kết quả 2026-09-17 bên dưới là lịch sử.
Road ParseShape hiện dùng FVector2D: lane mesh bị phẳng XY dù vehicle trace hỗ trợ elevation.
Native loader đếm tất cả XML lanes/junctions; Python index bỏ internal elements, nên 88.163/17.866
native records không so trực tiếp với 32.013/13.073 Python records. Đây không tự chứng minh map drift.
Catalog/profile runtime, streaming, TLS/semantic layers và capture chưa hoàn tất.
Mốc demo đầu dùng Editor trên máy hiện tại, chưa cam kết packaged/headless sensor delivery.
MCP là editor tooling tùy chọn, không là transport replay.

## Host and build

The detected engine is `D:\Starter Game\UE_5.8` (5.8.2). Build from repository root:

```powershell
& 'D:\Starter Game\UE_5.8\Engine\Build\BatchFiles\Build.bat' TrafficRenderEditor Win64 Development "-Project=$PWD\render_unreal\TrafficRender.uproject" -WaitMutex -NoHotReloadFromIDE
```

The 2026-09-17 build succeeded with `-MaxParallelActions=2` (98.73 seconds),
UE 5.8.2, MSVC 14.44 and Windows SDK 10.0.26100. The earlier missing NetFxSDK
blocker is resolved: the 4.8 SDK is registered on this host. On 2026-09-18, `vswhere`
confirmed both `Microsoft.Net.Component.4.8.SDK` and `Microsoft.Net.Component.4.8.TargetingPack`
in the existing Build Tools installation; the v4.8 reference-assembly directory is present.
A .NET runtime alone does not supply the SDK.

After a successful build, run the native contract tests:

```powershell
& 'D:\Starter Game\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' "$PWD\render_unreal\TrafficRender.uproject" -unattended -NullRHI '-ExecCmds=Automation RunTests TrafficRender.Bridge' '-TestExit=Automation Test Queue Empty' "-ReportExportPath=$PWD\render_unreal\Saved\Automation"
```

On 2026-09-17 all four native tests passed under `-NullRHI`, editor exit code 0:
contract self-test, replay interpolation, artifact fixture replay, and prepared-net
geometry. To opt into the retained real-network geometry check, append:

```powershell
"-TrafficRenderManifest=$PWD\render_unreal\Tests\Fixtures\retained_net_geometry\manifest.json"
```

That check requires the existing DVC/local SUMO network. It uses a two-frame
synthetic fixture trace, **not observed or calibrated map traffic**. The verified
network produced 88,163 lane meshes, 236,434 segments and 17,866 junction records.
The report is `Saved/Automation/index.json`, with `prepared_run_geometry.json`.
Without the argument `PreparedRun` reports that the optional check was not requested.
NullRHI verifies native parsing/geometry and replay mathematics, not RGB quality,
GPU performance, full interactive replay or sensor-image parity.

The engine-independent artifact validator is also executable:

```powershell
uv run python scripts/render/unreal_contract_smoke.py --manifest <prepared-render-run.json>
uv run pytest tests/integration/unreal -q
```

## Editor replay

Open `TrafficRender.uproject` after building. Add a `TrafficSumoGeometryActor` and
call its `BuildFromGeometryManifest` Blueprint function with the prepared geometry
manifest (a positive `MaxLanes` limits preview size). Add a `TrafficReplayController`,
set its absolute `ManifestPath`, `bAutoLoad` and `bAutoPlay`, and start editor play.
The play session advances recorded SUMO time; it does not simulate traffic.
Use `Seek` for deterministic inspection and `ExportQualityReport` for replay QA.

Launch the editor from repository root:

```powershell
& 'D:\Starter Game\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' "$PWD\render_unreal\TrafficRender.uproject"
```

MCP is configured for loopback port 8001 at `/mcp`; it becomes available only after
the editor loads successfully. It is an editor control surface, not trace streaming.
On 2026-09-17 its socket was verified at `127.0.0.1:8001`: protocol `2025-11-25`
initialize returned HTTP 200, initialized notification 202 and tools/list 200 with
`list_toolsets`, `describe_toolset` and `call_tool`. The test editor then exited
normally, so restart an editor session to use the endpoint. This does not claim
that a Codex MCP connection was installed or that toolset actions were exercised.
The project uses 100 centimetres per SUMO metre and subtracts the geometry origin.
Vehicle trace positions are front-bumper centres; replay shifts by half vehicle
length before placing each proxy. No lateral displacement is applied twice.

## RTX 3050 gameplay benchmark

Run `scripts/render/benchmark_city_level.py` from the canonical Unreal Editor after the target
level and assets are ready. In the Play dropdown, choose **New Editor Window (PIE)**, then use
**Tools > Execute Python Script…** and select the script. The script loads the
configured level, switches the play camera to the actor labeled `Retained City Hero Corner`, asks
the game viewport for 1920×1080 with `r.SetRes`, and verifies the actual game viewport size before
recording. Do not select **Simulate In Editor** or **Standalone Game**: the Editor Python callback
can access the in-process PIE world, while UE's Editor subsystem does not expose the separate
Standalone process world. The script warms up for 20 seconds, starts
`StartFPSChart`, samples for 60 seconds, calls `StopFPSChart`, and writes
`artifacts/tmp/city_pipeline/city_gameplay_benchmark.json`.

The report parses UE's per-frame FPS chart CSV from
`render_unreal/Saved/Profiling/FPSChartStats`. It contains Frame, GT, RT and GPU timings; P95 uses
nearest-rank. The `frame_time_gate` passes only when the game viewport is 1920×1080, the command log
confirms D3D12, all CSV timing rows are valid, at least 95% of GPU timings are non-zero, the captured
wall time, CSV time span and summed frame deltas are each at least 59 seconds, at least 1,500 frame
rows exist, and frame P95 is at most 33.3 ms. It records the `sg.*` quality settings, screen percentage, and before/after
`nvidia-smi` memory readings. VRAM is system-wide on this host. Per-frame frustum-visible counts are
not exposed by the available Python API, so `visible_count` is explicitly `null`; HISM/build-summary
totals in `scene_counts` are scene inventory, not visible draw counts. Since M1 requires visible
counts, `acceptance.passed` and `benchmark_completeness.complete` remain false while that metric is
unavailable, even if `frame_time_gate.passed` is true.

The old `SceneCapture2D` and Slate post-tick measurement remains available with
`AIQ_CITY_BENCHMARK_MODE=proxy`. Its report is diagnostic only and cannot satisfy gameplay-FPS
acceptance.

The path was checked against the installed UE 5.8.2 source: `Engine/Source/Runtime/Engine/Private/UnrealEngine.cpp`
routes `StartFPSChart` to per-frame recording, and `Engine/Source/Runtime/Engine/Private/ChartCreation.cpp`
writes the per-frame Frame/GT/RT/GPU CSV from `StopFPSChart`. The corresponding public arrays are in
`Engine/Source/Runtime/Engine/Public/ChartCreation.h`. Epic's [UEngine 5.8 API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UEngine),
[LevelEditorSubsystem Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/LevelEditorSubsystem),
[UnrealEditorSubsystem Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/UnrealEditorSubsystem),
[SystemLibrary Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SystemLibrary), and
[WidgetLayoutLibrary Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/WidgetLayoutLibrary)
document the editor play request, game-world access, console commands and game viewport size used by
the script.

Merge the table in `codex-mcp.example.toml` into the repository's
`.codex/config.toml`, preserving existing tables. Project-scoped configuration
loads for trusted projects. Start the built UE editor before reconnecting Codex;
`/mcp` reports connection status. This is a config example, not proof of a live
connection. See [OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

The UE config section and its four fields were checked against installed UE 5.8.2
`ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h`:
`ServerUrlPath`, `ServerPortNumber`, `bAutoStartServer`, `bEnableToolSearch`.
The class uses `config=EditorPerProjectUserSettings`, matching the checked-in INI.
The installed HTTPServer `HttpServerConfig.h` defaults its bind address to
`localhost`. No global MCP configuration was changed.
