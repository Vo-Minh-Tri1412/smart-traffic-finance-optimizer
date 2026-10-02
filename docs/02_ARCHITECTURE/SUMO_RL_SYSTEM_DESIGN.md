# Thiết kế RL trên map giữ nguyên

Cập nhật 2026-09-20. Phân biệt code scaffold với thiết kế mục tiêu.
Nguồn: `scripts/training/rl_sumo_train.py`, `rl/reward_profiles.py`,
`rl/map_economic_reward.py`, `simulation/engines/sumo/existing_net.py`.

## Hiện có

- CLI nhận DistrictSpec, scenario và reward profile; dry-run báo validation/blockers.
- Training export spec thành net mới bằng netconvert. Không có đường nhận retained project/net
  trực tiếp trong CLI này. Đổi spec ID không biến fixture thành map thật.
- SUMO-RL parallel_env, SuperSuit padding và vectorization dùng shared policy.
- PPO, frame-stack và RecurrentPPO là lựa chọn có code; chưa có kết quả so sánh trên retained map.
- SUMO-RL observation mặc định; chưa truyền project observation_class hay online geometry sensor.
- Reward kỹ thuật cũ hoặc map-economic callback incremental theo lane của từng signal.
- Có gate kiểm tra draft profile và hard constraints pending. Cờ acknowledge chỉ bỏ blocker,
  không thực thi emergency filter hoặc movement-aware safety.
- Existing-net runner chỉ hỗ trợ fixed_time. Rule-based của spec runner không đồng nghĩa
  có generic rule-based trên các nút thật.

## Mục tiêu được giữ

Demand từ hoạt động/tour, prepared net và định giá phải có cùng provenance.
Tối đa 8 TLS đủ điều kiện làm pilot; mọi xe và nút khác vẫn chạy trong mạng đầy đủ.
Không đòi điều khiển 100–160 nút hoặc chọn một bản đồ mới.

Observation thực tế cần đặc tả thứ tự feature, kích thước, padding, normalization,
missing state và thông tin được phép nhìn. [Observation proposal](OBSERVATION_SPACE_V1.md)
chưa là tensor runtime đã triển khai. Baseline oracle chạy trước; CV không là dependency bắt buộc.

Action chọn pha từ movement mapping thật. Runtime phải enforce minimum-green, clearance,
yellow/all-red và reject/hold padded actions không hợp lệ. Không suy action mask từ padding.
Emergency không được bỏ clearance. TLS chưa kiểm tra giữ baseline.

Reward mục tiêu dùng cost accrued toàn mạng, một ledger/environment:
`r_shared = -delta(A_accrued)/S`. Xem [objective](RL_QUBO_OBJECTIVE_RATIONALE.md).
Reward local hiện có là ablation/debug, không báo thành total VND. Không thêm queue/speed/priority
weights tùy ý vào objective chung. Safety và tiêu chí tiếp cận vẫn là điều kiện riêng.

## Thí nghiệm còn thiếu

1. Existing-net online control và action mapping/safety.
2. Demand/arrival/insertion/error ledger đầy đủ.
3. Mask-conditioned shared policy; nút ngoài mask giữ baseline.
4. Train/validation/test theo ngày/profile/seed và checkpoint selection độc lập.
5. Memoryless PPO, frame-stack 4, RecurrentPPO với reset đúng agent/episode.
6. Evaluator chạy lại cùng intended demand, routing assumptions, simulator settings và raw cost.
7. Nếu mở rộng sensor: observation lấy từ SUMO state hiện tại. Prerecorded baseline trace chỉ dùng
   offline; không thể thay state của policy đang làm thay đổi quỹ đạo.

Default cấu hình hiện tại không là quyết định model tốt nhất. Chưa chọn checkpoint thắng.
Không nhân bản cùng seed rồi coi các environment là mẫu độc lập.

## Liên kết QUBO

Protocol đầu tiên freeze shared checkpoint và evaluator trước khi đo singleton/pair.
Không train/fine-tune khác nhau theo mask rồi quy chênh lệch cho đầu tư.
Không dùng alternating optimization làm yêu cầu đợt đầu; xem
[protocol kép](MAP_AWARE_QUBO.md).

Các bước này là backlog có nghiệm thu trong [plan](SYSTEM_DELIVERY_PLAN.md),
không phải kết quả hoặc bảo đảm hội tụ.
