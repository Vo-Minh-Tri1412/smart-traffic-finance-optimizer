# RL training scaffold

Entry point: `rl_sumo_train.py`. Hiện nhận DistrictSpec rồi dựng net mới.
**Chưa nhận retained map/project để train trực tiếp**; không thay map thật bằng fixture.

```powershell
uv run python scripts/training/rl_sumo_train.py --spec tests/fixtures/specs/toy_public_district_v1.json --scenario normal_weekday --reward-profile configs/training/rl_reward_profile_v0.example.toml --out-dir artifacts/tmp/rl_training_scaffold --agent-mode multi_agent --memory lstm --dry-run
```

Có PPO/stack/LSTM, vectorization và reward gates. Observation còn là SUMO-RL default.
Không có upgrade-mask runtime, custom sensor observation hay evaluator full-map hoàn chỉnh.
Cờ override không thực thi các hard constraints còn pending. Chưa nên chạy training nghiên cứu
chỉ vì dry-run pass.

Xem [RL design](../../docs/02_ARCHITECTURE/SUMO_RL_SYSTEM_DESIGN.md) và
[audit](../../docs/04_STATUS/IMPLEMENTATION_STATUS.md).
