# Simulation backend: hai đường chạy chưa hợp nhất

Audit 2026-09-20. SUMO là nguồn traffic truth; reference backend chỉ là test double.
Không thay net giữ nguyên bằng DistrictSpec fixture.

| Đường | Hiện có | Giới hạn |
|---|---|---|
| DistrictSpec → exporter → netconvert → SUMO | Fixture export, fixed/rule runner, training scaffold | Dựng net mới; không phải retained map |
| district7.project.json → existing .net.xml → SUMO | Net index, validated polygon overlay, legacy demand/route tooling, fixed-time runner | Chưa có demand dataset trên polygon hiện tại; chưa rule/RL retained-net |

M0 TASK-095: simulation/maps/overlay.py đọc cả roi_semantic_overlay.v2 và semantic_overlay.v1,
không đổi schema hoặc suy ra cổng từ geometry. Validate descriptor thật pass; CLI báo demand missing,
2.588 polygon chưa có anchor. Smoke dừng trước routing khi không có flows. Cấu trúc hợp lệ chưa
chứng minh demand hành vi hoặc run nghiên cứu. Xem [audit A1](../04_STATUS/IMPLEMENTATION_STATUS.md).

## Ownership và package

- simulation/domain, specs: typed DistrictSpec và validation.
- simulation/maps: source index, overlay, demand, ROI utilities.
- simulation/routing: route policies; không phải simulator.
- simulation/engines/sumo: export/run/parse và existing_net runner.
- simulation/engines/reference: deterministic validation-only.
- simulation/metrics, traces: kết quả và replay artifacts.
- simulation/controllers: ID/contracts không bảo đảm mọi backend hỗ trợ mọi controller.

Parser hiện có waitingTime, TripInfo/FCD và aggregate metrics, nhưng bus occupancy=20,
failed_route_count/reroute_count=0 hard-code; chưa đối soát mọi intended trip.
Không dùng các trường đó như bộ đánh giá xã hội đã hoàn chỉnh.

Legacy simulation_trace_frame.v1 phục vụ aggregate/dashboard; native UE dùng vehicle_trace.v2.
Geometry/vehicle artifacts chạy được riêng; TLS/event/sensor schema registry không chứng minh
mọi producer đã chạy trên map thật. [Bridge contracts](RENDER_BRIDGE_CONTRACTS.md) sở hữu wire format.

## Lệnh kiểm tra

```powershell
uv run python -m ai_quantum_hvtc simulate validate-sumo-net --project simulation_projects/map_intake/district7.project.json
```

Lệnh trên kiểm tra map/overlay và báo riêng trạng thái demand; không chứng minh pipeline đã sẵn sàng.
Không bypass validation bằng fixture để báo demo chính thức.
[RL design](SUMO_RL_SYSTEM_DESIGN.md) và [plan](SYSTEM_DELIVERY_PLAN.md) giữ phần cần triển khai.

## Map snapshot trước thí nghiệm (M0, TASK-097)

```powershell
uv run python -m ai_quantum_hvtc simulate snapshot-sumo-project --project simulation_projects/map_intake/district7.project.json --out artifacts/tmp/m0_snapshot_097/project_snapshot.json
uv run python -m ai_quantum_hvtc simulate verify-project-snapshot --project simulation_projects/map_intake/district7.project.json --snapshot artifacts/tmp/m0_snapshot_097/project_snapshot.json
```

Lệnh tạo từ chối ghi đè: chọn output mới nếu snapshot đã tồn tại. `sumo_project_snapshot.v1`
giữ SHA256/byte size/path của descriptor, net, overlay và demand config; checksum toàn payload;
inventory tlLogic theo TLS ID/programID, toàn bộ phase/param attributes và connections theo
linkIndex với from/to/via lane IDs. Không tự tạo clearance hay gán nút eligible.
Verifier tính lại hashes và inventory, chặn input thay đổi dù chỉ whitespace; cho phép rebind
--project sang checkout khác chỉ khi byte sources giống hệt. Checksum phục vụ identity/corruption,
không phải chữ ký bảo đảm authenticity hoặc một kho bất biến trước sửa tay.

Retained map đã kiểm tra: 169 TLS/programs, 1.008 controlled connections, 649 phases, 0 signal
indices thiếu movement. Có 7 nhóm internal lanes trùng XML index nhưng ID riêng; snapshot ghi
`lane_index_ambiguities`, không sửa net. Connection from/to index mơ hồ bị chặn; via dùng lane ID.
Tất cả `control_review_status=pending`: inventory không chứng minh safety, connectivity phục vụ
demand hoặc 8 nút pilot. Đây mới là map snapshot, chưa là shared experiment/run manifest.
