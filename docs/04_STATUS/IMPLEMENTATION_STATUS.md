# Audit toàn project

## Cập nhật kết nối SUMO–Unreal 2026-10-02 (TASK-108)

Live launcher: scripts/render/run_sumo_unreal.py. Giữ nguyên net District 7 và route thử có sẵn;
SUMO sở hữu motion/TLS. UE nhận TCP frames, dựng đường thật và hiển thị xe/đèn. Catalog tài sản,
profile bố trí và profile cảnh là native UPrimaryDataAsset; BP_LiveVehicle/BP_LiveController mở rộng
presentation. Mesh/material/camera sửa trong Editor, save và khởi động lại run; không rebuild bridge.
JSON visual snapshot là bằng chứng của từng run, không là nguồn cấu hình song song.

Đã sửa non-uniform parent scale + child rotation làm méo xe: actor root không scale,
physical proxy giữ kích thước SUMO; visual giữ tỉ lệ, nằm trong envelope và căn đáy về ground plane.
Run GPU cuối artifacts/unreal_live/20261002-195628-970e2f pass 12 gate: 1.200 frames, 88.163 lanes,
1.008 signal heads, 668 lần đổi trạng thái TLS và pose/model-aspect/envelope khớp. Có video viewport
thật và capture timing. Hai run trước/sau edit Data Asset đổi sedan → van, FOV 65 → 52 với DLL hash
và mtime không đổi. Native build pass; 12 Python integration tests và 5 native contract tests pass;
Ruff/mypy pass. Kim chỉ nam được lưu trong AGENTS.md và UNREAL_ASSET_PIPELINE.md.

Giới hạn: route random không là demand đô thị đã hiệu chỉnh; đây là game viewport qua UnrealEditor,
chưa phải packaged executable. Nhà được người dùng chọn hoãn để hoàn thiện xe/cầu nối trước.
Kết nối này không nghiệm thu toàn bộ M1 thành phố/benchmark/sensor hay chuỗi nghiên cứu bên dưới.

Ngày: **2026-09-20**. Code nền: `4d32368`, nhánh `feature/unreal-map-economics-qubo`.
Phạm vi: Python/SUMO, demand/data, economics, RL, QUBO, sensors, UE C++, dashboard/frontend,
scripts/configs/tests và toàn bộ nhóm tài liệu. Audit code và kiểm tra local, không train model,
không chạy thí nghiệm lợi ích, không rebuild UE hoặc xác nhận lại dịch vụ cloud.

**Kết luận: có nhiều module nền chạy được riêng, chưa có pipeline nghiên cứu đầu-cuối trên map.**
TASK-095 (cùng ngày): CLI validate project đã pass với adapter polygon giữ provenance;
roundtrip vẫn dừng trước routing vì overlay hiện tại không có demand. Trước khi làm model,
cần hoàn thiện liên kết dữ liệu và bộ đo, không thêm thuật toán.

## 1. Từng phần có gì và thiếu gì

Cập nhật nghiên cứu reward (2026-09-20): đã đặc tả R1 cạnh baseline R0 trong
[objective rationale, mục 8](../02_ARCHITECTURE/RL_QUBO_OBJECTIVE_RATIONALE.md) và
presentation_draft.md (phần 8a–8f, liên kết QUBO ở slide 11). Có script kiểm tra số học
độc lập tại scripts/research/check_reward_design.py, không phải evaluator SUMO.
Chưa hiệu chỉnh hệ số địa phương, thay runtime, huấn luyện hay chứng minh lợi ích R1.

| Phần | Đã có trong code | Thiếu / giới hạn | Nguồn kiểm chứng |
|---|---|---|---|
| Map | Descriptor, SUMO net index, ROI prep, validated roi_semantic_overlay.v2 | 2.588 polygon chưa có anchors/flows; chưa có gate cơ sở đã review | `simulation/maps/source.py`, `overlay.py`, `roi.py`; TASK-095 |
| Demand | Parent inventory, prior time windows, generator volume/mix/duarouter; TASK-100 per-trip ledger cho flow synthetic khai báo tường minh | Chưa có người/hộ, hoạt động, tour, sở hữu/vị trí xe, occupancy và capacity calibration; retained map vẫn không có demand_flows | `scripts/data/prepare_demand_inventory.py`, `simulation/maps/demand.py` |
| SUMO | Spec export/run/parse, fixed/rule spec runner, existing-net fixed-time; TASK-099 giữ metric thiếu bằng chứng thành null; TASK-101 ghi runtime accounting cho managed debug run khi có optional intended ledger | Existing-net chưa rule/RL; retained-map intended/served-demand và route-failure ledger còn thiếu; bus passenger delay và failed-route count chưa khả dụng; reroute chỉ được tính khi mọi TripInfo row phát ra có `rerouteNo` hợp lệ | `simulation/engines/sumo/`, `experiments/runtime_accounting.py` |
| Economics | Typed profile, evidence/unit/price-year validation, resolution, coverage gates | Nearest edge không là cổng; thiếu OD/VOT/occupancy hiện hành đã hiệu chỉnh | `map_economics/` |
| Reward | Incremental timeLoss callback, monetary/scaled outputs riêng | Bỏ first sighting và xe giữa samples; không là cost toàn mạng | `rl/map_economic_reward.py`, `map_economics/reward.py` |
| RL | PPO/stack/LSTM, shared vectorization, dry-run và draft gates; TASK-102 chặn `action_filter_required`; TASK-103 giữ local action range; TASK-104 reserve training outputs exclusive | Net dựng từ spec; default observation; chưa có emergency preemption hoặc bằng chứng action safety đầy đủ, clearance safety evidence hay evaluator held-out | `scripts/training/rl_sumo_train.py`, `rl/reward_profiles.py`, `rl/action_guard.py` |
| QUBO map-aware | Signed OD impacts/pairs, budget slack, interval cases, exact solver và manifest | Chưa đo impacts, chưa portfolio replay/fit orchestrator, chưa tích hợp dashboard | `public_finance/map_qubo.py`, `scripts/finance/solve_map_qubo.py` |
| Finance legacy | Additive scores, exact/greedy và matrix đơn giản phục vụ fixture | Cắt adverse savings; QUBO không slack; không là bộ đánh giá chính | `public_finance/scoring.py`, `policy/algorithms/investment.py` |
| Geometry sensor | Cuboid rasterization, camera calibration, visible-count aggregation | Offline; không có tracker thực hoặc online RL adapter; confidence dựa truth visibility | `sensors/geometry_camera.py`, `scripts/sensors/run_geometry_camera.py` |
| CV | Dataset layout/label validation, notebook skeleton | Chưa exporter RGB/depth/instance UE, detector/tracker đánh giá, closed-loop camera | `sensors/synthetic_cv.py`, `scripts/data/`, `notebooks/` |
| Unreal | Manifest/trace loaders, unit transform, interpolation, cuboid replay, lane mesh, native tests | Chưa catalog/profile runtime, TLS/semantic visual layers, streaming, capture; lane mesh hiện XY | `render_unreal/Plugins/TrafficRenderBridge/Source/` |
| Dashboard | FastAPI, legacy run store/jobs, compare/finance APIs, React views; TASK-105 exclusive `RunStore.save_run`; TASK-106 read-only experiment index/verifier; TASK-107 sanitized sealed runtime-accounting view | `/api/experiments` remains separate from `/api/runs`; common TASK-098 experiment/run identity chưa bind/hash/verify qua dashboard; map/QUBO thật chưa nối | `dashboard/store.py`, `dashboard/config.py`, `dashboard/routers/`, `frontend/src/` |
| Hạ tầng dữ liệu | Git/uv, DVC pointers, TASK-096 reservation helper, TASK-097 project snapshot, TASK-098 experiment/run manifests và debug executor, TASK-099 metric-availability handling, TASK-100 synthetic-generator ledger, TASK-101 optional debug runtime trip accounting | Manifest giữ path/hash chứ không archive source/data; failed reservation không resume; chỉ debug được execute; outputs verified không đồng nghĩa nghiệm thu khoa học; retained-map intended/served-demand và route-failure ledger cùng runtime safety còn thiếu | `scripts/artifacts/`, `scripts/cloud/`, `ai_quantum_hvtc/experiments/` |

Đường dẫn Python trong bảng tính từ `ai_quantum_hvtc/`, trừ đường dẫn bắt đầu bằng scripts,
render_unreal, frontend, notebooks hoặc data.

## 2. Phát hiện ưu tiên

### A1 — Schema blocker đã sửa; demand vẫn thiếu (TASK-095)

Lệnh đã tái hiện lỗi trước sửa, nay exit 0:

```powershell
uv run python -m ai_quantum_hvtc simulate validate-sumo-net --project simulation_projects/map_intake/district7.project.json
```

Loader đọc riêng `roi_semantic_overlay.v2` và legacy `semantic_overlay.v1`; giữ nguyên raw payload,
geometry, parent IDs, tags và caveats. Kiểm tra ID trùng/rỗng, tọa độ hữu hạn, polygon có diện tích,
coordinate system, provenance và tham chiếu SUMO. Không tự sinh nearest-edge anchors.
Tài liệu bridge đã thay proposal `semantic_overlay.v2` bằng wire format thực; ROI utility v1 vẫn
chưa hỗ trợ. Constants Python/UE và render-contract smoke vẫn khai báo proposal cũ, chưa có
consumer overlay thực trong smoke; cần nối ở M1/M6, không coi contract smoke là nghiệm thu overlay UE.

Descriptor thật: 29.001 edges, 32.013 lanes, 13.073 junctions, 2.588 polygons/340 source parents;
1.354 entities có demand_enabled nhưng tất cả anchors rỗng, không có demand_flows. CLI báo
`demand_status: missing`. Smoke --no-dvc-pull dừng trước routing với `no demand_flows supplied`;
không sinh result/trace giả. Validation hình học là structural, không kiểm tra topology/cổng thực.

Bằng chứng local: `artifacts/tmp/m0_overlay_095/project_validation.json` và `input_hashes.json`.
Regression trên descriptor thật kiểm tra đủ entity/provenance và net/overlay byte-identical;
nếu thiếu DVC net thì test skip rõ ràng, không dùng fixture. Lượt này test thực đã chạy, không skip.

### A2 — Demand hiện tại chưa là mô hình hành vi

`_write_trips` tính round(volume * scenario_multiplier * vehicle_share), chia giờ đều,
luân phiên anchor edges. Không mô hình activity, tour, household, vehicle availability hay return.
Thiếu anchors bị skip trước attempted count; duarouter bật ignore-errors. Mẫu số QA chưa bao phủ
mọi nhu cầu dự định. Seed routing không biến cách tạo flow thành dữ liệu hành vi.

### A3 — Runtime và bộ đo chưa đủ để so model

Existing-net runner chỉ fixed_time, cho ignore-route-errors và teleport sau 300 giây.
Parser đọc TripInfo nhưng không đối soát toàn bộ intended demand/insertion queue. TASK-100 thêm
ledger per-trip ở bước sinh synthetic demand từ overlay `demand_flows` được khai báo rõ; ledger được ghi
trước khi gọi router, rồi đối soát đầu ra duarouter bằng vehicle ID khi output hợp lệ và vehicle có route
inline chứa edges không rỗng. Router lỗi hoặc
output không hợp lệ giữ demand ở trạng thái chưa xác minh với aggregate route counts là null. Đây là
provenance của synthetic assumption, không phải ledger demand/served của SUMO trên retained map.
TASK-099 giữ
`bus_passenger_delay_seconds` null vì `personCapacity` là sức chứa cấu hình, không phải occupancy
thực tế; `failed_route_count` cũng chưa khả dụng do chưa có nguồn sự kiện route failure.
`reroute_count` chỉ là tổng `rerouteNo` của các TripInfo row phát ra không rỗng khi mọi row đều
có giá trị hợp lệ; output rỗng hoặc thiếu/hỏng giá trị làm metric null. Report, API và UI giữ null;
finance scoring trả HTTP 422 nếu metric bắt buộc bị thiếu. `waitingTime` không phải toàn bộ thời gian hành trình.

TASK-101 thêm `runtime_accounting.json` có version/hash/identity cho managed debug run; khi được
cấp TASK-100 ledger thì đối soát routed IDs chính xác với route input và join TripInfo theo ID.
Không có ledger thì per-trip demand accounting tường minh unavailable, không sinh ledger từ routes.
Summary và Statistic output được ghi riêng thành aggregate vehicle/event counters; giá trị thiếu hoặc
không hợp lệ giữ null. Đây không phải person/occupancy metrics hay action-safety evidence. Research
gate vẫn đóng vì retained-map intended/served-demand, route-failure ledger và runtime safety còn thiếu.

### A4 — Có code training nhưng chưa có retained-map research environment

Training export_sumo_project + build_sumo_net, không dùng net hiện tại.
Không truyền custom observation_class; SuperSuit pad_action_space không phải safety mask.
Gate acknowledge_pending_hard_constraints không thực thi constraint.
Metadata `rl/contracts.py` còn public_finance_context, lệch với yêu cầu không lộ finance rank.
Chưa có orchestrator mask và shared network reward. Không chạy train nghiên cứu để vượt các thiếu hụt này.

### A5 — Hai đường finance không tương đương

Dashboard gọi legacy `score_candidates`, `optimize_exact/greedy`, `qubo_matrix`.
Legacy scoring dùng max(0, baseline-alternative), làm mất tác động xấu; cộng các kênh delay có nguy cơ
trùng và so lợi ích episode với capex/annual maintenance chưa có calendar tương ứng.
Legacy QUBO penalty là (cost-budget)^2 không slack, không biểu diễn upper-budget như module map-aware.
Module map-aware có tests signed effects/slack nhưng không tự đo coefficient.
Cần nối evaluator chung trước khi hiển thị ranking như kết quả nghiên cứu.

### A6 — Sensor hiện tại là surrogate, không phải detector thực

GeometryObservationAdapter lấy class/lane và visible_fraction từ ground truth visibility, đặt
confidence bằng trung bình visible_fraction và unknown_count=0. Đây là debug surrogate chưa hiệu chỉnh.
Chưa có tracker đo continuity, chưa đủ queue/wait/downstream features.
Không đưa các feature truth-derived vào camera policy rồi gọi là quan sát ảnh thực.
UE road ParseShape dùng FVector2D nên Z của lane mesh chưa được giữ, dù vehicle trace có elevation.

### A7 — Hạ tầng tái lập mới phân tán

run_manifest.template.json có trường rỗng. TASK-096 đã tái hiện và sửa prepare_run_dir ghi lại
metadata khi tái dùng ID: exclusive reservation, ID/stream validation, giữ partial folder để kiểm tra.
20 tests gồm concurrent creators, duplicate preservation, path/ID errors và failure recovery pass;
CLI tạo `artifacts/tmp/m0_lifecycle_096/rl/M0-LIFECYCLE-096` rồi lệnh lặp exit 1 đúng dự kiến.
Công cụ này vẫn chỉ là management scaffold, không được coi là research manifest hoặc kết quả.
Có checksum cục bộ ở map/profile/sync/QUBO, chưa có registry chung chống lẫn map/demand/checkpoint.
TASK-097 thêm `sumo_project_snapshot.v1`, create-exclusive CLI và verifier rehash/reinventory.
Artifact: `artifacts/tmp/m0_snapshot_097/project_snapshot.json`, checksum
`9762c47cc3c43bbe15217528530109ff3164ea66794a1ad3377248a50cd1be03`; snapshot/verify trên
descriptor thật pass. 21 targeted unit/integration tests pass, scoped Ruff pass.
Inventory thực: 169 TLS/programs, 1.008 controlled connections, 649 phases, 7 nhóm internal lane
indices mơ hồ được ghi lại; không có from/to controlled index mơ hồ hoặc signal index thiếu link.
Tất cả TLS vẫn pending control review; không chọn pilot hoặc sửa map trong bước này.
Tại thời điểm TASK-097, shared experiment manifest **chưa triển khai**; TASK-096 chưa chứng minh
full-run immutability. TASK-098 hiện thêm experiment/run schemas, input hashes, độc lập seed/case
splits, pairing/bindings và no-overwrite manifests; verifier kiểm tra output identity. Protocol giữ
R0/R1 thành reward profile riêng cùng evaluator profile theo objective manifest, còn reward runtime
chưa đổi. Source/data chỉ được tham chiếu bằng path/hash, không archive; reservation lỗi không
resume. Research execution vẫn bị gate đến khi có retained-map intended/served-demand và route-failure
ledger cùng runtime safety.

## 3. Kiểm tra thực hiện ngày audit

Sau TASK-095: `uv run pytest -ra` **194 passed**, 1 warning Starlette/httpx; 33 tests loader và
retained integration pass, scoped Ruff pass. Task manifest shape pass (`--skip-diff`);
không coi kiểm tra shape là kiểm tra phạm vi các thay đổi đã có sẵn trong working tree.
Net SHA256 `80637f09674799490eecfcd9ae1c9abe3f795795350ca3b61e8aa53d4d1f33e0`;
overlay SHA256 `9f596884721a3ccc956a929feabc83419816d9279a805ceb63a1b2edb331183a`.
Bảng dưới là snapshot **trước** sửa, không là trạng thái runtime hiện tại.

Sau TASK-096/097: full run có **232 passed, 1 failed** do test tài liệu còn yêu cầu câu
“chưa triển khai M0–M6”. Đã cập nhật assertion đúng trạng thái M0 đang triển khai và chạy lại
file đó: **3 passed**. Không còn failure đã biết; Ruff toàn `ai_quantum_hvtc scripts tests`
và scoped diff whitespace pass. Tổng collection hiện 233 tests; vẫn 1 warning Starlette/httpx.
Không chạy lại toàn suite chỉ để đổi con số full-run. Thay đổi mới chưa commit; tài liệu có
thay đổi sẵn từ người dùng nên không stage/commit gộp. Các task 095–097 đã ghi phạm vi riêng.

TASK-098 hoàn tất phần identity hạ tầng ngày 2026-09-27; M0 tổng thể vẫn chưa nghiệm thu. Scoped
acceptance có **88 passed** gồm actual SUMO toy-fixture execution và test research execution bị
gate; full `uv run pytest -ra` có **320 passed**, 1 Starlette/httpx deprecation warning. Scoped Ruff pass. Full Ruff hiện báo lỗi
import-order có sẵn trong `scripts/presentation/build_canva_motion.py`, ngoài scope task; file
được giữ nguyên. Scoped `git diff --check` pass; kiểm tra toàn repo chỉ báo dòng trắng cuối
`render_unreal/Config/DefaultEngine.ini`, thay đổi có sẵn cũng được giữ nguyên.

Experiment retained-map identity được tạo và verify tại
`artifacts/tmp/m0_identity_098/experiments/M0-RETAINED-IDENTITY-098`, checksum
`ab4188d8775eae37f827a4bba9a334a536f62787dd381ddf5f231f4d7c9986c5`, khóa 98 source files và
đúng hash net/overlay đã snapshot. Đây chỉ là identity debug: **0 run** được tạo vì map có
`demand_flow_count=0`; toy fixture integration không phải kết quả nghiên cứu. Các con số cũ bên
dưới và snapshot TASK-095–097 ở trên vẫn là evidence lịch sử.

TASK-099 được chấp nhận như hạ tầng xử lý metric availability ngày 2026-09-27, sau **8 focused
unit tests**, **1 real-SUMO integration test**, scoped Ruff, scoped mypy (`--follow-imports=silent`),
frontend typecheck và scoped `git diff --check` đều pass. Bus passenger delay tiếp tục null vì
`personCapacity` không đo occupancy thực; reroute count chỉ tính khi tất cả TripInfo row không rỗng
đều có `rerouteNo` hợp lệ; failed-route count còn unavailable. Null được giữ qua report/API/UI và
finance scoring trả HTTP 422 khi thiếu metric bắt buộc. Repo-wide diff-check vẫn bị chặn bởi dòng
trắng cuối có sẵn, ngoài scope task, trong `render_unreal/Config/DefaultEngine.ini`; scoped diff-check
đã pass. TASK-100 bổ sung ledger chỉ cho requested synthetic vehicle trips từ explicit overlay
flows; nó không thêm retained-map demand, SUMO served-demand/route-failure ledger hoặc runtime
safety evidence. Research gate vẫn đóng và M0 chưa hoàn tất.

TASK-101 được chấp nhận như hạ tầng runtime accounting cho managed debug run: **21 focused unit tests**
và **1 real-SUMO integration test** pass, gồm một trip đã đến và nhánh TripInfo chưa xác minh;
scoped Ruff, scoped mypy (`--follow-imports=silent`) và scoped diff-check pass. SUMO 1.27.1 phát
`vaporized=""` cho trip đã đến (arrival hợp lệ, attr được xử lý như không có vaporization evidence)
và `vaporized="end"` ở nhánh kết thúc run chưa đến đích; giá trị thứ hai giữ `unverified`, không
được đoán là unfinished. Artifact chỉ áp dụng cho per-requested-vehicle-trip cùng whole-simulation
vehicle/event counters, không suy ra người/occupancy hoặc xác nhận safety. No-ledger case giữ
accounting unavailable. Retained-map demand/route-failure ledger và runtime-safety evidence vẫn thiếu;
research gate đóng, M0 chưa hoàn tất.

TASK-102 khóa đường acknowledge cho hard constraint chưa triển khai có enforcement
`action_filter_required`, kể cả khi `hard_constraints_block_training=false`; enforcement không được hỗ trợ
cũng trả validation blocker. Dry-run vẫn in blocker và ID constraint. Training-path regression xác nhận
export SUMO, build net, dựng environment và tạo policy đều chưa được gọi khi thiếu emergency action filter.
Không triển khai preemption, action mask hay clearance logic và không xác nhận runtime safety; research
gate vẫn đóng, M0 đang triển khai. Acceptance: 9 focused unit/CLI tests, scoped Ruff, scoped mypy
(`--follow-imports=silent`) và scoped diff-check pass.

TASK-103 ghi lại local discrete action counts trước SuperSuit padding và thêm guard trước vectorization.
Invalid/padded action chỉ được hold ở green phase hiện tại nếu signal xác nhận non-yellow và phase hợp lệ;
thiếu state thì toàn batch fail-closed trước khi SUMO tiến. Log v1 được exclusive-reserve cho run, ghi
và flush ý định submit replacement trước `env.step` để lỗi ghi không thể đi trước mô phỏng; clone của
vectorized env có `env_instance_id` riêng, ổn định trong log chung. Interval lấy trực tiếp từ spec và
phải `delta_time > yellow_time`, khớp assertion của SUMO-RL 1.4.5. Unit test kiểm tra fake clone/batch
và logging; integration test dùng fixture intersection đóng gói của SUMO-RL, chỉ chứng minh plumbing.
Không có emergency preemption hoặc tuyên bố action/runtime safety hoàn chỉnh; TASK-102 tiếp tục chặn
training. Research gate đóng và M0 vẫn đang triển khai. Acceptance: 33 focused unit/CLI/integration tests
(gồm 1 real-SUMO-RL smoke), scoped Ruff, scoped mypy (`--follow-imports=silent`) và scoped diff-check pass.

TASK-104 claim `--out-dir` bằng exclusive directory creation chỉ sau mọi training blockers và trước
SUMO export/netconvert, environment hoặc policy. Existing/partial run fail trước export, giữ nguyên
sentinel; không resume hoặc cleanup. Mỗi subdirectory và `training_manifest.json` cũng được tạo bằng
exclusive create. Regression xác nhận dry-run và hard-constraint blocker không tạo output directory.
Acceptance: 35 focused unit/CLI/integration tests, scoped Ruff, scoped mypy
(`--follow-imports=silent`), scoped diff-check, manifest TOML parse và allowed-path whitespace scan
pass. TASK-102 vẫn chặn actual training; không đổi reward/profile, research gate vẫn đóng và M0 chưa
hoàn tất.

TASK-105 `RunStore.save_run()` atomically reserves its run directory before serializing result, trace,
or metadata. Existing/partial IDs fail with `FileExistsError` before serializers; sentinel bytes stay
unchanged and concurrent same-ID writers yield one owner. Existing API/schema/run-ID validation is
unchanged. This does not connect dashboard runs to TASK-098 experiment identity, manifests, hashes or
verified-output contracts; that integration remains unfinished. Acceptance: 16 focused dashboard
RunStore/API/metric tests passed, including concurrent reservation (one unrelated Starlette/httpx
deprecation warning); scoped Ruff, mypy, diff-check, task TOML parse and allowed-path whitespace scan
passed. Research gate remains closed and M0 is still in progress.

| Kiểm tra | Kết quả | Phạm vi chứng minh |
|---|---|---|
| `uv run pytest -ra` | 163 passed, 1 Starlette/httpx deprecation warning | Tests hiện có, không có test giữ toàn project descriptor thật |
| `uv run ruff check ai_quantum_hvtc scripts tests --output-format concise` | Pass | Lint, không chứng minh đúng mô hình |
| `npm run typecheck` tại frontend | Pass | TypeScript compile checks, không UI/visual QA |
| validate-sumo-net với --project | Fail A1 | Integration blocker có thể tái lập |
| validate-sumo-net với --sumo-net đường net gốc | Pass | 29.001 external edges, 32.013 external lanes, 13.073 non-internal junctions, 169 traffic_light junctions |
| Doctor | Exit 0, 3 cảnh báo legacy governance optional | Không kiểm tra integration overlay thật |
| Markdown local links | 40 tracked Markdown files ngoài coordination; 0 broken file links | Không kiểm tra URL ngoài/heading anchors |
| Whitespace | Scoped git diff --check pass | Loại trừ DefaultEngine.ini có thay đổi trước audit |
| Overlay JSON inspection | 2.588 entities, 340 source parents | Parent là ứng viên grouping, chưa là cơ sở/capacity được xác minh |

Python index loại internal edges/junctions. Native UE cũ đếm tất cả XML lanes/junctions nên số
88.163 lanes/17.866 junction records trong log lịch sử không cùng mẫu số. 169 ở Python là đếm
junction type traffic_light, không thay cho inventory unique tls_id/program/linkIndex hoàn chỉnh.
Không có chứng cứ mới về calibrated OD, trained policy hay measured portfolio benefits.

Native build/4 automation tests và MCP discovery ngày 2026-09-17 là lịch sử, **không chạy lại**
ngày audit. NullRHI không chứng minh hình ảnh/FPS. Source reviews 2026-09-16/17 được giữ nguyên
ngày kiểm chứng, chưa xác minh lại lịch xe, giá, giấy phép hoặc liên kết mạng.

## 4. Tài liệu đã hợp nhất và định hướng bị loại

- Xóa ENVIRONMENT_DESIGN_RESEARCH_PLAN.md: kế hoạch chọn/vẽ môi trường cũ đã bị thay bằng map cố định.
- Xóa PUBLIC_SERVICE_DISTRICT_ENVIRONMENT_SPEC.md: map I01–I20, multiplier tùy ý, reward trộn
  và danh sách mở rộng chưa có căn cứ không còn là spec hiện hành. Nguyên tắc demand có mục đích,
  taxonomy và prior giờ có nhãn assumption được giữ trong demand design/config, không mất provenance.
- Hợp nhất rồi xóa 7 docs trùng: MULTI_AGENT_RL_MEMORY_TRAINING → SUMO_RL_SYSTEM_DESIGN;
  QUBO_RL_JOINT_OPTIMIZATION → MAP_AWARE_QUBO; STRUCTURED_OCCLUSION_AND_SENSOR_RL và
  OPTICAL_SENSOR_TARGET → SYNTHETIC_VISUAL_SENSOR_DATASET; MAP_ROI_AUTO_ZONING_PIPELINE →
  MAP_ECONOMIC_DATA_MODEL; UNREAL_RENDER_MIGRATION_PLAN → render_unreal/README và bridge;
  DVC_DATA_MANAGEMENT → DATA_ARTIFACT_WORKFLOW. Tên ở đây là lịch sử cleanup, không là link.
- Tổng cộng xóa 9 docs, thư mục docs giảm từ 30 xuống 21 Markdown files; không tạo archive khác. Viết lại index theo hai điểm vào:
  audit (hiện có/thiếu) và plan (làm tiếp theo). Giữ riêng schema/source reviews có vai trò khác.
- Gỡ yêu cầu ROI khoảng 100–160 nút, graph/CTDE và alternating optimization khỏi kế hoạch đợt đầu.
- Gỡ phát biểu streaming UE đã có, observation đầy đủ đã triển khai, finance legacy là QUBO chính.
- Không giữ đề xuất departDelay + timeLoss làm primary objective cạnh tranh với elapsed-time ledger.
- CV không chặn baseline oracle. UE là tooling, không một model nghiên cứu độc lập.
- Giữ source reviews, bridge contracts, tests fixture và historical task manifests có giá trị kiểm toán.
  Tuổi tài liệu không tự chứng minh nội dung sai; không xóa nguồn/lịch sử chỉ để hết tên cũ.

Docs bị xóa có thể khôi phục từ Git. Không xóa data/map/assets hoặc các thay đổi UE chưa commit.
Audit chỉ thay tài liệu và locator nguồn, không sửa runtime để che lỗi vừa tìm.

## 5. Thứ tự tiếp theo

1. Contract/schema integration của descriptor thật và regression đã xong trong TASK-095.
2. Nối lifecycle experiment/run vào các runner research, dashboard và training; debug executor
   hiện chưa đủ điều kiện nghiên cứu.
3. Xây activity/tour demand và validation bảo toàn, ledger intended/served demand.
4. Existing-net baseline/safety/evaluator, rồi RL pilot.
5. Đo tác động và kiểm định QUBO. Tích hợp dashboard từ cùng run.
6. UE assets có thể làm song song; sensor/CV mở rộng khi có hợp đồng observation và capture QA.

Điểm tiếp tục sau TASK-107 đã đổi theo chỉ đạo 2026-09-28: làm thành phố OSM→SUMO→UE,
sau đó nối cùng map/run vào dashboard trước demand hành vi; RL/QUBO tạm hoãn. `RunStore` legacy và
`/api/experiments` vẫn chưa có identity/job chung. Retained map chưa có `demand_flows`; nghiên cứu
RL/QUBO và các tuyên bố hiệu quả vẫn bị chặn bởi demand/route-failure ledger và runtime safety.

TASK-106 adds an opt-in read-only experiment view at `/api/experiments`; it uses only
`AIQ_DASHBOARD_EXPERIMENTS_DIR`. If unset, the API reports `not_configured` and does not fall back to
toy/fixture data. The index verifies direct-child experiment directories, skips symlinks and exposes
identity/status metadata plus `discovered_run_ids`; those IDs are directory names only and do not mean
their runs are verified. `GET /api/experiments/{experiment_id}/runs/{run_id}` calls the existing
verifiers on demand and reports `unsealed`, `outputs_verified` or a generic `verification_failed`, with
output roles/hashes only and no absolute input paths. This remains separate from legacy `/api/runs` and
does not bind dashboard jobs/store to common experiment identity, translate into `SimulationResult`,
recalculate reward/finance, write artifacts, or change the research gate. Acceptance: focused dashboard
and experiment-store tests passed (**74 passed**, with one unrelated Starlette/httpx deprecation warning);
scoped Ruff, mypy, diff-check, task TOML parse and allowed-path whitespace scan also passed. M0 remains
in progress and the research gate remains closed.

TASK-107 adds a sanitized runtime-trip-accounting view under the same opt-in experiment API. It is
available only after the run is sealed and every output hash is verified; an unsealed run returns before
reading the payload, and a sealed run without the `runtime_accounting` output role reports unavailable.
The store reader verifies once, reads only a declared safe relative role, then checks the returned bytes'
SHA-256 and length against `outputs.json`. The API accepts only `runtime_trip_accounting.v1`, identity
matching the run, and typed selected fields. It preserves null counters and exposes demand/aggregate
status, counts, summary time, statistic counters and known limitations; `source_inputs`,
`source_outputs`, errors, arbitrary JSON, and per-trip rows are omitted. It includes the explicit caveat
that simulator collision counts do not establish complete action safety. No metrics are recomputed and
no research/safety acceptance is implied. Acceptance: 61 focused API/store tests passed (one unrelated
Starlette/httpx deprecation warning), scoped Ruff, mypy, diff-check, TOML parse and allowed-path
whitespace scan passed. Research gate remains closed and M0 remains in progress.

### City pipeline, 2026-09-28 — đang triển khai

Net giữ lại được tái tạo từ OSM gốc bằng profile `netconvert` 1.27.1 mà file net ghi trong header.
Phần XML `<net>` của ứng viên và net giữ lại trùng byte, SHA-256
`09893b501fa014ea8bc5d97d98bddbc57c8b0b622a6e309988bed9e159163529`; header sinh tự động
khác. `scripts/maps/rebuild_retained_osm_net.py` tạo ứng viên/QA riêng, không thay net. Map-only
geometry manifest và visual placement manifest nằm trong `render_unreal/CitySources/`; 1.087 vị trí
công trình minh họa nằm trong polygon road-clipped, 1.234 neutral không bị gán thành công viên/cây.
Đây không phải building footprints khảo sát hay demand.

Unreal 5.8 build và native tests đã đọc 88.163 lane/236.410 đoạn hợp lệ theo 305 tile 500 m
(24 đoạn suy biến được báo riêng). Ảnh GPU 1920×1080 ở `artifacts/tmp/city_pipeline/city_overview_tiled.png`
cho thấy toàn mạng đường; `city_hero_initial.png` cho thấy camera gần với HISM khối placeholder.
Ảnh gần hiện **chưa đạt** chuẩn hình tham chiếu: thiếu mặt tiền PBR, vỉa hè, đạo cụ/ánh sáng và
vehicle/TLS replay nhìn thấy. Tiling/culling đã có, nhưng mesh Cube chỉ có LOD0, chưa đo benchmark
60 giây/P95 trên RTX 3050 4 GB. Các `.umap` generated ở `render_unreal/Content/City/` bị ignore;
không coi screenshot hoặc native parsing là nghiệm thu cảnh thành phố.

Debug run `CITY-VISUAL-20260928/CAR-REPLAY-SMOKE-001` dùng 100 route random chỉ để thử xe.
SUMO seal/hash verify; 600 frame `vehicle_trace.v2`/100 ID qua Python render-contract smoke và UE
native `PreparedRun`. Summary cuối: 100 inserted, 47 arrived, 53 running; demand accounting
`unavailable` do không có intended-demand ledger. UE chưa trình diễn xe của run này trong level,
dashboard/frontend chưa gắn cùng ID. Executor nay chặn trace không có hình học canonical trước
khi seal render output. Không dùng số smoke này để kết luận giao thông đô thị.

Xem [kế hoạch nghiệm thu](../02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md).
