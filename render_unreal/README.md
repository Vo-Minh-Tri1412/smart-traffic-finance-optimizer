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

The 2026-09-16 build attempt stops in UBT rules before C++ compilation because the
host lacks the .NET Framework SDK required by `SwarmInterface`. Install the
`.NET Framework 4.8 SDK` component through the existing Visual Studio Build Tools
installation, then rerun this command. A .NET runtime alone does not supply this SDK.
No installer or machine configuration change is performed by this repository.

After a successful build, run the native contract tests:

```powershell
& 'D:\Starter Game\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' "$PWD\render_unreal\TrafficRender.uproject" -unattended -NullRHI '-ExecCmds=Automation RunTests TrafficRender.Bridge' '-TestExit=Automation Test Queue Empty' "-ReportExportPath=$PWD\render_unreal\Saved\Automation"
```

These native tests have not yet run on this host. The engine-independent artifact
validator is executable now:

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
