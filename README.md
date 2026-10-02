# Smart Traffic Public Finance Optimizer

Dự án nghiên cứu bốn bài toán: **Demand hành vi, RL điều khiển tín hiệu, QUBO đầu tư
và Computer Vision tùy chọn**. SUMO là môi trường mô phỏng; Unreal là lớp hiển thị/cảm biến,
không phải game và không phải nguồn quyết định giao thông.

## Đọc gì trước

- [Audit toàn project](docs/04_STATUS/IMPLEMENTATION_STATUS.md): code hiện có, phần thiếu,
  rủi ro và bằng chứng kiểm tra ngày 2026-09-20.
- [Thiết kế demand](docs/02_ARCHITECTURE/CURRENT_ROI_DEMAND_DATASET_DESIGN.md):
  người/hộ/cơ sở, lịch hoạt động, phương tiện và chuỗi đi–về.
- [Kế hoạch triển khai](docs/02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md): phụ thuộc và nghiệm thu.
- [Mục tiêu chung RL/QUBO](docs/02_ARCHITECTURE/RL_QUBO_OBJECTIVE_RATIONALE.md).
- [Mục lục docs](docs/README.md).

## Bốn bài toán liên kết

| Bài toán | Đầu vào và vai trò | Trạng thái |
|---|---|---|
| Demand | Hoạt động của người/hộ/doanh nghiệp tạo tour, OD, giờ và phương tiện | Có inventory và generator flow để smoke; chưa có activity/tour generator |
| RL | Điều khiển pha hợp lệ trên cùng demand, giảm cost toàn mạng | Có scaffold PPO/frame-stack/LSTM từ DistrictSpec; chưa có retained-net pilot |
| QUBO | Chọn danh mục đầu tư từ hiệu ứng can thiệp, chi phí và ngân sách | Có builder/solver map-aware; chưa đo singleton/pair trên map |
| CV tùy chọn | Ước lượng observation từ ảnh, đo ảnh hưởng sai số lên điều khiển | Có geometry camera offline và template; chưa có chuỗi detector closed-loop |

Giữ nguyên map trong `simulation_projects/map_intake/district7.project.json`.
Python đếm 169 junction loại traffic_light, chưa là inventory TLS/program hoàn chỉnh;
pilot dự kiến tối đa 8 nút đủ điều kiện, không cắt map.
**Hiện validate project thất bại do schema overlay lệch loader**, dù validate net riêng pass.
Tên District 7 trong file là tên nguồn, không chứng minh ranh giới hành chính.

Demand synthetic có giả định minh bạch được dùng cho nghiên cứu, không được gọi là OD quan sát
hoặc đã hiệu chỉnh. Chưa có bằng chứng RL thắng baseline, lợi ích đầu tư thực tế hoặc ưu thế lượng tử.

## Cấu trúc code

- `ai_quantum_hvtc/simulation/`: spec fixture, retained-net loader, SUMO runner/parser và traces.
- `ai_quantum_hvtc/map_economics/`: provenance, valuation, coverage, evaluator incremental.
- `ai_quantum_hvtc/rl/`, `scripts/training/`: reward và scaffold huấn luyện.
- `ai_quantum_hvtc/public_finance/map_qubo.py`: QUBO map-aware chính.
- `ai_quantum_hvtc/policy/`, `public_finance/scoring.py`: đường legacy/fixture, không dùng làm kết luận kinh tế.
- `ai_quantum_hvtc/sensors/`: geometry visibility và validation layout dataset.
- `ai_quantum_hvtc/dashboard/`, `frontend/`: FastAPI/React; mặc định vẫn là fixture.
- `render_unreal/`, `render_assets/`: adapter UE và nguồn assets dùng chung.

## Kiểm tra local

```powershell
uv sync
uv run python -m ai_quantum_hvtc doctor
uv run pytest
uv run python -m ai_quantum_hvtc simulate --help
```

SUMO là dependency hệ thống. Unreal chỉ cần cho render, không cần để chạy unit tests.
Xem [UE README](render_unreal/README.md), [training scaffold](scripts/training/README.md)
và [frontend](frontend/README.md) cho lệnh riêng.

Hai đường simulation hiện khác nhau: DistrictSpec được export thành net mới để kiểm thử;
existing-net dùng net thật nhưng chỉ hỗ trợ fixed-time. Không dùng đường đầu thay map đã chốt.
Dashboard và finance fixture chưa nối vào pipeline đầu tư map-aware hoàn chỉnh.

Git giữ source/config nhỏ; dữ liệu lớn và output theo [DVC](docs/02_ARCHITECTURE/DATA_ARTIFACT_WORKFLOW.md).
Các manifest hiện còn phân tán, chưa có experiment registry toàn hệ thống.
