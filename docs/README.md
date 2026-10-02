# Tài liệu dự án

Cập nhật sau audit 2026-09-20. Không cần đọc toàn bộ: bắt đầu bằng **hai tài liệu**:

1. [Audit: từng phần có gì, thiếu gì, lỗi nào đang chặn](04_STATUS/IMPLEMENTATION_STATUS.md).
2. [Kế hoạch tiếp theo và điều kiện nghiệm thu](02_ARCHITECTURE/SYSTEM_DELIVERY_PLAN.md).

## Tra cứu theo việc cần làm

| Chủ đề | Tài liệu chính |
|---|---|
| Mục tiêu bốn bài toán | [Project target](00_TARGETS/PROJECT_TARGET.md) |
| Bài toán nghiên cứu, dùng để giới thiệu | [Brief](01_PROJECT_BRIEF/SMART_TRAFFIC_PUBLIC_FINANCE.md) |
| Demand người–hoạt động–tour | [Demand design](02_ARCHITECTURE/CURRENT_ROI_DEMAND_DATASET_DESIGN.md) |
| Map/facility/định giá | [Economic data model](02_ARCHITECTURE/MAP_ECONOMIC_DATA_MODEL.md) |
| SUMO: spec runner khác existing-net | [Backend](02_ARCHITECTURE/SIMULATION_BACKEND_ARCHITECTURE.md) |
| RL và memory | [RL design](02_ARCHITECTURE/SUMO_RL_SYSTEM_DESIGN.md), [observation proposal](02_ARCHITECTURE/OBSERVATION_SPACE_V1.md) |
| Objective dùng chung | [Reward rationale](02_ARCHITECTURE/RL_QUBO_OBJECTIVE_RATIONALE.md) |
| QUBO và protocol đo tác động | [Map-aware QUBO](02_ARCHITECTURE/MAP_AWARE_QUBO.md) |
| Render ownership / wire formats | [Bridge framework](02_ARCHITECTURE/SUMO_RENDER_BRIDGE_FRAMEWORK.md), [contracts](02_ARCHITECTURE/RENDER_BRIDGE_CONTRACTS.md) |
| UE assets/config mở rộng | [Asset pipeline](02_ARCHITECTURE/UNREAL_ASSET_PIPELINE.md), [build/run](../render_unreal/README.md) |
| Geometry sensor và CV tùy chọn | [Sensor/dataset contract](02_ARCHITECTURE/SYNTHETIC_VISUAL_SENSOR_DATASET.md) |
| Artifacts, DVC, Drive | [Data workflow](02_ARCHITECTURE/DATA_ARTIFACT_WORKFLOW.md) |

## Nguồn tham khảo, không phải kết quả mô hình

- [Travel source review](02_ARCHITECTURE/CURRENT_ROI_TRAVEL_SOURCE_REVIEW.md).
- [Economic source review](02_ARCHITECTURE/MAP_ECONOMIC_SOURCE_RESEARCH.md).
- [Competition snapshot](03_COMPETITION/AI_QUANTUM_HVTC_FACTS.md).

Nguồn giữ ngày kiểm chứng gốc; audit không tự xác nhận lại nguồn mạng hoặc biến prior thành dữ liệu thật.
Task manifests trong coordination/tasks giữ bằng chứng lịch sử, không là kế hoạch hiện hành.

## Quy tắc giữ tài liệu gọn

- Trạng thái hiện tại chỉ tổng hợp ở audit; dependencies/acceptance ở plan.
- Mỗi domain có một chủ sở hữu nội dung; không tạo thêm plan/migration/proposal lặp cùng quyết định.
- Schema chi tiết và source reviews giữ riêng vì có chức năng khác, không phải đọc nhập môn.
- Nội dung sai bị loại; phần có ích của docs trùng được hợp nhất rồi xoá bản cũ, không tạo archive mới.
- Target/contract không chứng minh đã implement; code/test/run mới là bằng chứng.
- Lịch tuần và phân công trên taskboard không được coi là đã đồng bộ chỉ vì có docs local.
