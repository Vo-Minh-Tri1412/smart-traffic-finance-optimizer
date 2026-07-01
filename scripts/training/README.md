# RL Training Scaffold

This folder contains cloud-oriented entrypoints for SUMO-RL training.

Use `rl_sumo_train.py` in dry-run mode first. It validates the district spec and reward profile
without training or writing model artifacts:

```powershell
uv run python scripts/training/rl_sumo_train.py `
  --spec tests/fixtures/specs/toy_public_district_v1.json `
  --scenario normal_weekday `
  --reward-profile configs/training/rl_reward_profile_v0.example.toml `
  --out-dir artifacts/tmp/rl_training_scaffold `
  --dry-run
```

Actual training is intended for Google Colab or Kaggle, with outputs written to Drive/Kaggle
working storage. The script refuses local training unless explicitly overridden.

The reward profile is a draft contract. Economics and CS should edit the weights, approve the
profile, and implement pending hard constraints such as emergency vehicle preemption before making
policy claims from RL results.
