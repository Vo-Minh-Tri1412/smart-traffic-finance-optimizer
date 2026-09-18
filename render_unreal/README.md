# SUMO Unreal adapter

This UE 5.8 project consumes the repository's SUMO render contracts. Traffic motion
and decisions remain owned by SUMO. The current implementation provides lane mesh
ingestion and canonical cuboid vehicle replay; sensor-image export, visual semantic
zones and traffic-light layers are not implemented yet.

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
