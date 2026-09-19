# Kế hoạch hoàn thiện hệ thống SUMO–Unreal–RL–QUBO

Ngày chốt: **2026-09-19**. Trạng thái: **thiết kế đã thống nhất, chưa triển khai M0–M6**.
Lượt lưu tài liệu không phải phê duyệt số liệu kinh tế, huấn luyện model hoặc hoàn tất render.
Theo yêu cầu bổ sung cùng ngày, renderer cũ được loại bỏ thay vì giữ làm fallback.

## 1. Quyết định đã chốt

- Giữ nguyên net và semantic overlay hiện tại; không thay bằng ranh giới hành chính hoặc map toy.
  Inventory ghi nhận 169 TLS, không đồng nghĩa mọi TLS đã đủ điều kiện điều khiển RL.
- Pilot 8 nút đầu tư/điều khiển, toàn bộ map và giao thông vẫn chạy; các nút khác giữ baseline.
- UE bán thực, tương tác trên máy RTX 3050 4 GB hiện tại. Chỉ dùng tài nguyên/assets miễn phí.
- Demand synthetic minh bạch được dùng cho nghiên cứu khi chưa có OD hiện hành đủ tin cậy.
  Không gọi giả định là quan sát hoặc đã hiệu chỉnh; tiếp tục tìm nguồn và ghi bất định.
- Oracle và geometry visibility trước; RGB/depth/instance dataset và YOLO sau.
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
| Dashboard | Đọc kết quả, provenance, trạng thái và caveats; không tính lại reward riêng |

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

Freeze map/overlay hashes, inventory TLS/movements/programs và các nguồn đầu vào. Đồng bộ docs;
tách debug, research_synthetic và production-claim gates. Rà parser hard-code occupancy bus 20,
bộ đếm lỗi giả bằng 0, dashboard fixture-default và script cảnh minh họa đang dở.

Nghiệm thu: đầu vào được kiểm tra; research/demo chính thức không âm thầm dùng fixture hoặc
placeholder. Runtime safety không được bỏ qua chỉ vì chọn synthetic mode.

### M1 — Assets và demo UE trên đúng map

Triển khai catalog/profile, importer/validator và actor components. Đọc lane/junction/Z từ net;
thiếu cao độ phải gắn flat assumption. Mapping đầu đèn theo tls_id/linkIndex, không timer độc lập.
Tile mesh, instancing, pooling và streaming theo vùng nhìn; sensor giữ đủ occluders độc lập LOD
camera trình diễn. Chọn góc ở một pilot TLS đã kiểm tra; kiến trúc chưa đo đạc chỉ là minh họa.

Nghiệm thu: đổi mesh xe/cụm đèn trong Editor không sửa logic; có ảnh 1920×1080 và replay trace SUMO,
không mất texture hoặc sai pose/TLS. Benchmark 60 giây sau warm-up, target P95 frame time ≤33,3 ms
ở preset 1080p trên máy hiện tại; ghi GPU memory, visible count và preset. Không cắt mất xe để đạt FPS.
Preset daylight/dusk riêng sensor; ray tracing không bắt buộc.

### M2 — Demand theo cơ sở và biên map (song song M1)

Hoàn thiện parent facility, cổng có hướng/mode/connectivity; không coi nearest-edge là cổng thật.
Tách capacity/trip rate/calendar/mode share/occupancy/evidence. Giữ 11 mục đích và bin 15 phút;
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

### M4 — RL pilot và geometry sensor

Chọn tối đa 8 TLS đủ điều kiện từ development baseline: nút person-delay cao nhất, mở rộng các
nút kết nối theo delay, hòa điểm bằng ID. Không đủ 8 connected eligible nodes thì báo số thật,
không đổi map. Freeze pilot trước test. Một shared policy có mask cục bộ; so PPO memoryless,
frame-stack 4 và RecurrentPPO. Geometry observation đọc SUMO hiện tại trong vòng kín, không đọc
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

### M6 — Sensor dataset, YOLO và tích hợp bàn giao

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
