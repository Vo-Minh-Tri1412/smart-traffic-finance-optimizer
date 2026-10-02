# Kế hoạch hoàn thiện hệ thống SUMO–Unreal–RL–QUBO

Điều chỉnh ưu tiên 2026-10-02: hoàn thành kết nối SUMO → Unreal trực tiếp trên map giữ lại.
Catalog tài sản, profile bố trí và profile cảnh phải sửa bằng Editor/Data Asset/Blueprint.
Đổi mesh/material/camera không phải sửa/build bridge. TASK-108 nghiệm thu bằng live game viewport,
pose/time/TLS từ SUMO và thử đổi profile không rebuild; ảnh dàn dựng không thay thế bằng chứng.
Các gate demand/RL/QUBO và chất lượng thành phố hoàn chỉnh không chặn mốc kết nối này.

Cập nhật tiến độ: **2026-09-28**. Bốn bài toán nghiên cứu dài hạn: demand hành vi, RL vận hành,
QUBO đầu tư, CV tùy chọn.

Ưu tiên bàn giao hiện tại do người dùng đổi: giữ ROI/net đã chốt; hoàn thiện nguồn OSM và cách
tái dựng SUMO, dựng thành phố trong UE với assets chỉnh được, camera tầm phố, LOD/culling và đo
hiệu năng trên RTX 3050 4 GB. Dùng route random đã có chỉ để thử xe/trace; dữ liệu này không là
demand đô thị. Sau khi map/replay đạt, nối cùng map/run vào dashboard/UI. M2 demand và các mốc
RL/QUBO tạm hoãn đến sau chuỗi này. Phần M6 liên quan dashboard/map/run được làm sớm hơn các
phần M6 nghiên cứu và sensor; không coi đó là nghiệm thu M6 toàn bộ.

Ngày chốt thiết kế: **2026-09-19**. Trạng thái: **M0 đang triển khai; M1–M6 chưa nghiệm thu**.
Lượt lưu tài liệu không phải phê duyệt số liệu kinh tế, huấn luyện model hoặc hoàn tất render.
Theo yêu cầu bổ sung cùng ngày, renderer cũ được loại bỏ thay vì giữ làm fallback.

## 1. Quyết định đã chốt

- Giữ nguyên net và semantic overlay hiện tại; không thay bằng ranh giới hành chính hoặc map toy.
  Python đếm 169 junction loại traffic_light, chưa thay thế inventory TLS ID/program/link.
- Pilot 8 nút đầu tư/điều khiển, toàn bộ map và giao thông vẫn chạy; các nút khác giữ baseline.
- UE bán thực, tương tác trên máy RTX 3050 4 GB hiện tại. Chỉ dùng tài nguyên/assets miễn phí.
- Demand synthetic minh bạch được dùng cho nghiên cứu khi chưa có OD hiện hành đủ tin cậy.
  Không gọi giả định là quan sát hoặc đã hiệu chỉnh; tiếp tục tìm nguồn và ghi bất định.
- Oracle trước; geometry visibility và CV là mở rộng, không chặn nghiên cứu RL–QUBO.
- Mốc đầu mở trên máy hiện tại bằng một lệnh, chưa yêu cầu bộ cài không có Unreal Editor.
- SUMO là simulator; UE không quyết định giao thông, RL hoặc economics. MCP chỉ phục vụ Editor,
  không phải transport trace và không phải điều kiện để pipeline chạy.

Đích bàn giao: scenario → baseline/RL → cost toàn mạng → QUBO → kiểm định lại → cùng run trong UE
và dashboard. Ảnh đẹp ở mốc đầu không chứng minh chuỗi nghiên cứu đã hoàn tất.

## 2. Kiến trúc và hợp đồng

| Lớp | Nguồn sự thật / trách nhiệm |
|---|---|
| SUMO | Tuyến, chuyển động, pha đèn, sự kiện và traffic metrics |
| Data/Economics | Facility/OD, demand, occupancy, định giá, nguồn và assumptions |
| RL | Hành động hợp lệ; không quyết định ngân sách đầu tư |
| QUBO | Danh mục đầu tư từ tác động biên đã đo và ngân sách |
| Unreal | Assets, materials, replay, camera và sensor export |
| Dashboard | Đọc kết quả, provenance, trạng thái và caveats; không tính lại reward riêng. TASK-105 reserve local `RunStore.save_run`; TASK-106 thêm experiment view read-only; TASK-107 chỉ hiển thị sanitized runtime accounting đã sealed/hash-verified. Vẫn tách biệt với `/api/runs` và identity chung |

UE dùng ba nhóm Data Assets: asset catalog, placement profile, scene profile. ID, mesh/Blueprint,
materials, physical envelope, pivot/axis, LOD, source/license và attachments phải rõ ràng. Source
GLB/PNG nằm trong `render_assets/`; JSON snapshot chỉ phục vụ kiểm toán, không cạnh tranh với Data
Assets làm nguồn cấu hình mỹ thuật. Xem [đặc tả assets](UNREAL_ASSET_PIPELINE.md).

Giữ tương thích các contract geometry/vehicle/TLS/camera/render đã có. Bổ sung trong implementation:

- Demand dataset: scenario/day/seed/trip/tour/leg, facility/external-zone OD, gate, purpose,
  intended departure/arrival, mode, occupancy, ordered route, valuation và evidence.
- Network ledger: pending/running/arrived/error/teleport, thời gian và cost mỗi chuyến.
- Experiment manifest: map/demand hashes, seeds, controller/checkpoint/mask, observation/reward/
  economic versions và liên kết output. Không tái tạo net thật từ DistrictSpec fixture.

## 3. Các mốc và điều kiện nghiệm thu

### M0 — Chốt nền tảng

Tương thích overlay đã sửa trong TASK-095: project roi_semantic_overlay.v2 được validate với
geometry/provenance giữ nguyên; legacy semantic_overlay.v1 vẫn riêng. Descriptor thật pass,
nhưng 2.588 polygon chưa có cổng và chưa có demand; smoke dừng rõ ràng trước routing.
TASK-096 chặn tái dùng run directory trong helper; TASK-097 snapshot/verify descriptor, net,
overlay, demand config và TLS/program/movement inventory. TASK-098 bổ sung experiment/run
manifest có schema, path/hash, seed/case split độc lập, pairing và bindings cho input, profile,
checkpoint, output; create/prepare-run/prepare-debug/verify-experiment/verify-run/run-debug là
CLI hiện có. Manifest giữ tham chiếu path/hash, không archive source/data; reservation lỗi không
resume. Render manifests chỉ là metadata, chưa chạy Unreal. Hạ tầng identity chưa nghiệm thu M0;
execution chỉ mở cho fixed-time debug vì retained-map intended/served-demand ledger và runtime safety
còn thiếu.
TASK-099 được chấp nhận cho xử lý metric availability: bus passenger delay vẫn unavailable vì
`personCapacity` không phải occupancy thực tế; `reroute_count` là tổng `rerouteNo` trên các TripInfo
row phát ra không rỗng chỉ khi mọi row đều có giá trị hợp lệ; `failed_route_count` vẫn unavailable
do chưa có nguồn sự kiện. Result/report/API/UI giữ null; finance scoring trả HTTP 422 khi metric bắt
buộc bị thiếu. TASK-099 không bổ sung intended-demand/route-failure ledger hay runtime safety evidence,
nên research gate vẫn đóng và M0 vẫn đang triển khai.

TASK-099 acceptance evidence: 8 focused unit tests, một real-SUMO integration test, scoped Ruff,
scoped mypy và frontend typecheck đều pass; scoped `git diff --check` cũng pass. Repo-wide diff-check
bị chặn bởi dòng trắng cuối có sẵn, không liên quan trong `render_unreal/Config/DefaultEngine.ini`.
TASK-100 bổ sung versioned per-requested-vehicle-trip ledger cho synthetic generator khi explicit
overlay `demand_flows` đã có; route đầu ra được đối soát theo ID. Đây là provenance của giả định
synthetic, không phải calibrated field demand hoặc retained-map ledger; không tự tạo flow/anchor.
Retained map vẫn thiếu demand_flows và runtime safety evidence, nên research gate đóng, M0 chưa hoàn tất.
TASK-100 acceptance: 45 focused tests pass, gồm một real-SUMO test xác nhận trip ID được giữ làm
vehicle ID đầu ra kèm inline route có edges không rỗng (chỉ xác nhận plumbing, không phải
traffic/research evidence); scoped Ruff và scoped mypy pass. Vehicle thiếu route hợp lệ bị fail-closed.
Ledger pending được ghi trước routing, và router lỗi/output lỗi giữ aggregate route counts null. Freeze các nguồn đầu vào
còn lại. Đồng bộ docs; tách debug, research_synthetic và production-claim gates. Tiếp tục ledger,
runtime safety, dashboard fixture-default và script cảnh minh họa đang dở.

TASK-101 thêm `--intended-demand-ledger` tùy chọn cho managed debug run và đóng băng input này;
không truyền ledger thì per-trip demand accounting là unavailable, không suy ledger từ routes.
`runtime_accounting.json` lưu identity/hash, đối soát routed IDs với route input, join TripInfo và
giữ rows chưa xác minh khi output thiếu/lỗi. Summary/Statistic counters được ghi riêng ở scope
vehicle/event toàn mô phỏng; không suy occupancy/person metrics hay xác nhận action safety. Test với
SUMO 1.27.1 xác nhận trip tới đích có arrival hợp lệ và `vaporized=""`; case chưa tới đích phát
`vaporized="end"`, không phải boolean tài liệu, nên vẫn unverified. TASK-101 không thêm retained-map
demand/route-failure ledger hoặc runtime-safety evidence: research gate đóng, M0 đang triển khai.
Acceptance: 21 focused unit tests, 1 real-SUMO integration test, scoped Ruff, scoped mypy
(`--follow-imports=silent`) và scoped diff-check pass.

TASK-102 làm pending hard constraint có enforcement `action_filter_required` không thể được bỏ qua
bằng `--acknowledge-pending-hard-constraints` hoặc `hard_constraints_block_training=false`; enforcement
không được hỗ trợ trả validation blocker. Dry-run nêu rõ blocker/constraint ID và test train chứng minh
SUMO export, net build, environment, policy chưa bắt đầu. Đây chỉ là training gate: chưa thêm emergency
preemption, action filter runtime hoặc bằng chứng clearance safety. Research gate vẫn đóng, M0 vẫn đang
triển khai. Acceptance: 9 focused unit/CLI tests, scoped Ruff, scoped mypy
(`--follow-imports=silent`) và scoped diff-check pass.

TASK-103 lưu số action hợp lệ từng agent trước khi SuperSuit padding, rồi chặn invalid/padded discrete
action ở wrapper nằm sau padding và trước vectorization. Chỉ thay action bằng green phase hiện tại khi
signal xác nhận không-yellow và phase còn trong action range; nếu không đọc được phase, batch fail-closed
trước bước SUMO. JSONL `rl_action_intervention.v1` dành riêng cho run được reserve exclusive, ghi và
flush trạng thái replacement đang được submit trước `env.step`; sự kiện có `env_instance_id` ổn định
theo từng clone vectorized. I/O log lỗi cũng chặn step. `delta_time > yellow_time` được kiểm tra trên
giá trị spec thô vì SUMO-RL 1.4.5 yêu cầu điều kiện nghiêm ngặt này. Test với packaged
2way-single-intersection chỉ xác nhận plumbing. Guard không thực hiện emergency preemption hay chứng minh
action safety đầy đủ; TASK-102 vẫn chặn training khi emergency filter chưa có. Research gate đóng, M0
đang triển khai. Acceptance: 33 focused unit/CLI/integration tests, gồm 1 real-SUMO-RL smoke; scoped
Ruff, scoped mypy (`--follow-imports=silent`) và scoped diff-check pass.

TASK-104 reserve `--out-dir` bằng atomic `mkdir(exist_ok=False)` sau khi training/runtime/map blockers
đã qua, nhưng trước SUMO export/netconvert, environment hoặc policy. Directory có sẵn, kể cả partial
run, fail trước export; files sentinel không bị sửa, không resume/cleanup. Subdirectories và
`training_manifest.json` cũng được tạo exclusive. Dry-run và training blocker vẫn trả về trước mọi
reservation/write. Đây chỉ là lifecycle guard: TASK-102 tiếp tục chặn actual training và research gate
vẫn đóng, M0 đang triển khai. Acceptance: 35 focused unit/CLI/integration tests pass; scoped Ruff,
scoped mypy (`--follow-imports=silent`), scoped diff-check, TOML parse và allowed-path whitespace scan
pass.

TASK-105 làm `RunStore.save_run()` reserve `<runs_dir>/<run_id>` bằng exclusive directory creation
trước gọi serializers; duplicate/partial run ID fail mà không sửa sentinel, resume hoặc cleanup. Concurrent
save cùng ID chỉ cho một writer. API/schema và ID format giữ nguyên. Đây là hardening của local dashboard
file store, không phải tích hợp common experiment/run identity: store chưa bind/hash/verify manifest của
TASK-098 hoặc đồng bộ API/job với ledger. Acceptance: 16 focused RunStore/API/metric tests passed
(gồm concurrent reservation; một cảnh báo deprecation Starlette/httpx không liên quan), scoped Ruff,
scoped mypy, scoped diff-check, manifest TOML parse và allowed-path whitespace scan đều pass. M0 vẫn
đang triển khai; research gate không đổi.

TASK-106 bổ sung catalog/verifier chỉ đọc cho experiment manifests dưới thư mục do operator cấu hình
tường minh bằng `AIQ_DASHBOARD_EXPERIMENTS_DIR`. Khi unset, API trả `not_configured`, không chọn fixture
hoặc quét repo. `/api/experiments` chỉ liệt kê thư mục con trực tiếp, bỏ symlink/đường dẫn ra ngoài,
đối chiếu `verify_experiment()` và trả identity/status; `discovered_run_ids` chỉ là tên thư mục trực tiếp,
chưa xác minh nội dung run. Endpoint
`/api/experiments/{experiment_id}/runs/{run_id}` kiểm tra ID và containment, sau đó gọi `verify_run()`
đúng lúc được yêu cầu. Run chưa seal giữ trạng thái `unsealed`; run sealed chỉ báo `outputs_verified` sau
kiểm tra hash, với output role/hash/size. Manifest hỏng trả trạng thái lỗi generic, không lộ đường dẫn
input tuyệt đối. Endpoint không ghi/xóa/chạy, không dựng `SimulationResult`, không tính lại reward/finance,
không đổi schema của legacy `RunStore` hay gắn API/job vào common experiment identity. TASK-106 là
integration view read-only, chưa phải common identity integration. Acceptance: 74 focused dashboard và
experiment-store tests passed (một cảnh báo deprecation Starlette/httpx không liên quan), scoped Ruff,
mypy, diff-check, task TOML parse và allowed-path whitespace scan đều pass. M0 vẫn đang triển khai;
research gate vẫn đóng.

TASK-107 thêm `GET /api/experiments/{experiment_id}/runs/{run_id}/runtime-accounting`. Endpoint chỉ đọc
role `runtime_accounting` nếu `verify_run()` xác nhận `outputs_verified`; run `unsealed` trả sớm không đọc
payload và thiếu role thì unavailable. Store có helper xác minh một lần, chỉ resolve declared relative
path an toàn, đọc bytes rồi kiểm tra SHA-256 và length của chính bytes trả về so với outputs manifest để
chặn TOCTOU. Parser chỉ chấp nhận `runtime_trip_accounting.v1`, identity đúng run và kiểu dữ liệu đã
chốt; null vẫn null. API chỉ trả execution/evidence status, demand status/scope/reason/counts, aggregate
scope/status, summary counters/time, statistic counters và limitations đã biết. Không lộ source paths,
errors, arbitrary JSON hoặc per-trip rows. Limitation nêu rõ simulator collision counts không chứng minh
complete action safety. Đây là presentation của artifact đã verify, không phải metric recomputation,
action-safety validation hoặc research acceptance. Acceptance: 61 focused dashboard/API/store tests
passed (một cảnh báo deprecation Starlette/httpx không liên quan), scoped Ruff, mypy, diff-check, task
TOML parse và allowed-path whitespace scan đều pass. M0 vẫn đang triển khai; research gate đóng.

Nghiệm thu: đầu vào được kiểm tra; research/demo chính thức không âm thầm dùng fixture hoặc
placeholder. Runtime safety không được bỏ qua chỉ vì chọn synthetic mode.

### M1 — Assets và demo UE trên đúng map

Triển khai catalog/profile, importer/validator và actor components. Đọc lane/junction/Z từ net;
thiếu cao độ phải gắn flat assumption. Mapping đầu đèn theo tls_id/linkIndex, không timer độc lập.
Tile mesh, instancing, pooling và streaming theo vùng nhìn; sensor giữ đủ occluders độc lập LOD
camera trình diễn. Chọn góc ở một pilot TLS đã kiểm tra; kiến trúc chưa đo đạc chỉ là minh họa.

Nghiệm thu: đổi mesh xe/cụm đèn trong Editor không sửa logic; có ảnh 1920×1080 và replay trace SUMO,
không mất texture hoặc sai pose/TLS. Benchmark acceptance dùng game viewport PIE in-process và CSV
per-frame Frame/GT/RT/GPU từ `StartFPSChart`/`StopFPSChart`: warm-up 20 giây, lấy mẫu 60 giây,
viewport thực 1920×1080, D3D12, ≥95% GPU sample khác 0, CSV span/wall-time/frame-delta ≥59 giây và
ít nhất 1.500 frame rows; target P95 frame time ≤33,3 ms trên preset hiện hành. Ghi VRAM, preset và visible count.
Nếu thiếu visible count, chỉ đánh dấu frame-time gate; benchmark M1 vẫn incomplete. Script hiện hỗ
trợ PIE in-process qua New Editor Window; Standalone separate-process chưa được Editor Python callback
điều khiển. Editor + SceneCapture/Slate tick chỉ là chẩn đoán, không là nghiệm thu gameplay. Không
cắt mất xe để đạt FPS.
Preset daylight/dusk riêng sensor; ray tracing không bắt buộc.

Theo yêu cầu visual mới, ảnh góc phố trên map thật phải được so trực tiếp với ảnh tham chiếu
`artifacts/unreal_demo/signal_corner.png`: camera tầm đường, mặt tiền/cửa sổ/vỉa hè có vật liệu PBR,
đèn và bố cục rõ. Kenney/Cube placeholder không được dùng làm chất lượng bàn giao. Tài sản gần
camera dùng mesh có LOD thật khi đáng giảm tam giác; tường vốn rất ít vertex có thể giữ LOD0 nhưng
phải dùng instancing/culling. Mọi tài sản nhập ghi nguồn/license và không đổi đường, xe, TLS truth.

### M2 — Demand theo cơ sở và biên map (song song M1)

Hoàn thiện parent facility, cổng có hướng/mode/connectivity; không coi nearest-edge là cổng thật.
Tách capacity/trip rate/calendar/mode share/occupancy/evidence. Sinh người/hộ/hoạt động trước,
ràng buộc lịch, nơi thường xuyên và quyền sử dụng xe; sinh tour/leg rồi ánh xạ sang xe SUMO. Giữ 11 mục đích và bin 15 phút;
phân bố giờ trong các khung, tour đi/về, xe rỗng, đưa đón và hoạt động qua nửa đêm. Tách II/IE/EI/EE,
external endpoint khỏi entry/exit connector. Low/base/high là thay đổi tham số công bố, không tune
để tạo hình ảnh tắc đường. WorldPop là prior lịch sử, không trực tiếp thành chuyến từng building.

Nghiệm thu: seed tái lập, không nhân capacity theo polygon, đối soát người/xe/chuyến và route;
requested failures vẫn trong mẫu số. Mỗi số có nguồn hoặc assumption register, năm/đơn vị/license.
Chi tiết tại [demand design](CURRENT_ROI_DEMAND_DATASET_DESIGN.md).

### M3 — Runner thật, safety và ledger

Mở existing-net runner sang movement-aware rule-based và RL; dùng lại net, không dựng toy net.
Enforce minimum-green, transition/clearance theo TLS; nút chưa được kiểm tra giữ baseline.
Invalid/padded actions phải bị chặn/hold và log, emergency cũng phải qua clearance.
Ledger nối intended demand, runtime events và TripInfo gồm unfinished; bỏ occupancy và error-count
hard-code. Tách demand window/drain-out; hết giới hạn thì báo unserved và lower bound.

Nghiệm thu: mỗi chuyến dự định có trạng thái; thử nghẽn đầu vào/route lỗi/teleport không tạo ra
tiết kiệm giả. Bus occupancy và passenger records không bị cộng hai lần.

### M4 — RL pilot oracle; geometry sensor tùy chọn

Chọn tối đa 8 TLS đủ điều kiện từ development baseline: nút person-delay cao nhất, mở rộng các
nút kết nối theo delay, hòa điểm bằng ID. Không đủ 8 connected eligible nodes thì báo số thật,
không đổi map. Freeze pilot trước test. Một shared policy có mask cục bộ; so PPO memoryless,
frame-stack 4 và RecurrentPPO. Khi có nhánh sensor, geometry observation phải đọc SUMO hiện tại trong vòng kín, không đọc
prerecorded baseline trace cho policy đang thay đổi quỹ đạo. Tách oracle/camera; không lộ hidden
IDs/counts, purpose, future state hoặc finance rank. Train headless không cần UE.

Nghiệm thu: cùng demand/settings giữa baseline và RL; reset recurrent state đúng environment;
so nhiều seed và nhóm. Báo trung thực nếu RL không thắng. Không tune bằng test.

### M5 — QUBO tác động đo được

Freeze shared mask-conditioned checkpoint và evaluator. Với 8 nút, đo empty + 8 singleton + 28 pair
= 37 masks/scenario/seed. Giữ cả adverse OD effects. Hold out mask từ 3 nút trở lên để đo surrogate
error. Exact pilot, so greedy/CPU heuristic; mở rộng không tuyên bố optimality/quantum advantage.
Re-run selected portfolios trên test sau khi đã freeze tuning; kiểm tra ngân sách, phục vụ và nhóm.

Nghiệm thu: mọi hệ số truy được về run/hash/checkpoint/profile; portfolio được kiểm định ngoài fit.
Thiếu calendar/capex/opex/hiện giá thì chỉ báo nghiên cứu giả định, không khuyến nghị đầu tư thực tế.
Xem [protocol QUBO](MAP_AWARE_QUBO.md) cho seed splits và kiểm tra signed interactions.

### M6 — Tích hợp bàn giao; sensor dataset/YOLO tùy chọn

Xuất RGB/depth/instance cùng camera/time/state bằng Editor batch; không hứa Object IDs trong
shipping build. Test bus/truck occlusion, truncation, stable IDs và label visibility; không dùng
projected rectangles thay depth mask. Nhãn hình ảnh không được dự đoán vai trò kinh tế vô hình.
Split theo run/day/scenario/camera, không random các frame liền kề. Train YOLO bằng tài nguyên
miễn phí sau dataset QA; đầu tiên đánh giá detector và hiệu chỉnh sai số, không claim closed-loop
detector control khi chưa kiểm chứng ảnh → observation → action thực sự.

Một lệnh mở UE/dashboard cùng experiment/run; dashboard đọc ledger và QUBO thật, hiển thị
synthetic/evidence/missing state. Không seed fixture hoặc tự fallback sang dữ liệu mẫu trong demo
chính thức. Khôi phục được run từ manifest và dữ liệu đã phiên bản hóa.

## 4. Objective chung cho RL/QUBO

**R0 / R1:** Công thức cơ sở dưới đây giữ làm R0 cho pilot. Đề xuất nghiên cứu R1
(lịch hoạt động, ràng buộc đuôi chậm trễ/mức phục vụ, potential shaping) được đặc tả cùng
nguồn, dữ liệu tối thiểu và ablation tại [objective rationale, mục 8](RL_QUBO_OBJECTIVE_RATIONALE.md).
Objective manifest khóa R0/R1 thành reward profiles riêng, cùng dùng evaluator profile. Reward
runtime hiện tại chưa đổi. Chưa bỏ các gate dữ liệu/ledger. Chỉ bật thành phần đủ bằng chứng;
R1 chưa được huấn luyện và chưa chứng minh tốt hơn R0. Không tạo một kế hoạch triển khai trùng.

Với demand/route/occupancy và mốc tham chiếu cố định:

```text
A = sum_v n_v * w_v * T_v / 3600
C = A - sum_v n_v * w_v * T0_v / 3600
r_shared(t) = -delta(A_accrued)/S
B_i = F(0) - F(i)
I_ij = F(i) + F(j) - F(i,j) - F(0)
```

T là thời gian intended departure → arrival gồm insertion wait; T0 là mốc cố định. Mỗi environment
thu một ledger, không cộng bản sao reward của các agent. Khi served demand đầy đủ, C khác A bởi
hằng số nên không cần thưởng arrival tùy ý. Scale S cố định trong experiment; raw C/person-delay
mới là evaluator, không dùng discounted/clipped return để báo VND. Unfinished phải báo riêng.

QUBO tối thiểu hóa capex/opex trừ lợi ích hiện giá, cộng budget penalty có slack. F chỉ annualize
khi có calendar/scenario weights. Multiplier service/flow giữ 1; không tính cả giá trị lô hàng hoặc
doanh thu building thành tiết kiệm. Reliability/cargo/emissions/schedule chưa có bằng chứng thì
chưa bật, không diễn giải là tác động bằng 0. Báo person-delay và tiếp cận thiết yếu theo nhóm;
không khuyến nghị portfolio vi phạm tiêu chí đã chốt trước test hoặc thiếu bằng chứng đánh giá.

Local incremental reward hiện tại giữ làm ablation. Team reward chống đẩy nghẽn khỏi vùng đo nhưng
khó credit assignment hơn; không che kết quả bằng weights tùy ý. Xem
[objective rationale](RL_QUBO_OBJECTIVE_RATIONALE.md) để phân biệt code hiện tại và thiết kế mới.

## 5. Phân công, kiểm thử và rollout

Ba luồng chuyên trách: UE/assets/sensors; Data/Economics; QUBO/impact experiments. Integrator sở hữu
SUMO safety/ledger/RL/dashboard/contracts. M0 trước; M1 và M2 song song; M3 chặn M4/M5. Ảnh demo
có thể bàn giao ở M1; kết quả nghiên cứu chỉ sau các gate tương ứng.

Mỗi task có manifest, phạm vi file, tests và commit riêng trên nhánh UE hiện có. Không nhiều owner
cùng sửa một schema. Git giữ source/config/docs, Git LFS giữ UE packages nhỏ, DVC/Drive giữ dữ liệu
lớn/model/output. Không mua assets/GPU hoặc cài plugin không cần thiết. Lịch tuần/deadline vẫn thuộc
taskboard; tài liệu này lưu quyết định kiến trúc và acceptance, không sao chép lịch quản lý.

Tests bắt buộc: unsupported schema/hash/ID; asset replacement/coordinates/TLS; conservation và
cross-boundary/overnight/uninserted/unfinished; observation leakage và recurrent reset; invalid
actions; QUBO exact-energy/budget/signed effects; cùng run ID từ ledger đến dashboard/UE.

Các tham số nghiên cứu chưa có bằng chứng (volume, occupancy, scale, clearance, financial horizon,
ngưỡng nhóm) phải được ghi và kiểm tra trong profile trước run; tài liệu này không phê duyệt ngầm
các placeholder. Runtime và calibration chỉ được đánh dấu hoàn thành bằng evidence kiểm thử/run.
