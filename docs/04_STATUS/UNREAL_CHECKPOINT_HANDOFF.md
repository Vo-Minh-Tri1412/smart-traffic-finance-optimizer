# Unreal checkpoint — 2026-10-02

Branch: feature/unreal-map-economics-qubo. Keep the PR in draft; do not merge into main,
which still uses Godot. This checkpoint includes the branch's earlier research/backend work.

## Run and edit

Pull Git LFS packages, restore the retained SUMO net through the existing DVC workflow,
install SUMO, and use Unreal 5.8.2. From the repository root:

    uv run python scripts/render/run_sumo_unreal.py --engine-root "D:/Starter Game/UE_5.8"

The launcher opens a live Unreal game viewport. SUMO owns all motion/TLS. F toggles following;
WASD/QE and right mouse move/look. Native catalog, placement and scene Data Assets under
Content/LiveTraffic/Profiles own appearance; save and restart the run to apply edits without
rebuilding C++. Blueprint hooks extend presentation. AGENTS.md records the guiding principles.

## Verified checkpoint

- Win64 native build succeeded. Live run 20261002-210344-a7a868 passed all 16 gates.
- 1,200 frames, 88,163 rendered lanes, 1,008 heads and 668 TLS state changes; canonical pose agrees.
- 6,137 OSM footprint building parts, 664,013 marking segments, 392,304 sidewalk segments,
  and 58,840 globally generated instanced trees. These counts are scene inventory, not visible count.
- Heights and landscaping are editable visual assumptions. Confirmed road-overlap footprints and
  footprints outside the retained map were excluded; missing junction geometry still limits clearance QA.
- Vehicle physical proxy and visual root are separate; model proportions and ground contact preserved.
- Editor test replaced sedan with van and FOV 65 with 52 without changing the native DLL.
- Scoped Python/native checks passed; frontend typecheck passed.
- Full pytest: 414 passed, 2 failed, 1 skipped. Failures: managed debug experiment trace geometry
  fixture/runtime compatibility, and task-manifest fields missing in TASK-102.
- Full mypy has existing errors in older editor/research helper scripts; full Ruff needs cleanup.

## Continue here

The city layer is a functional visual checkpoint, not finished urban art or an accepted FPS benchmark.
Improve sparse/fragmented sidewalk coverage, tree material/readability and camera framing; do not
stage traffic or change the retained simulation map. Validate a per-building height edit in Editor.
Keep no-merge status until the Unreal/Godot migration is intentionally reviewed.

Large curated Unreal packages and frozen urban source geometry use Git LFS. Logs, videos, cache,
the duplicate render_unreal 5.8 checkout and personal Giay_to/tmp files remain local.
