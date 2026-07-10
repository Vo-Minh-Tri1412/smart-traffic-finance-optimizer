# RL Training Scaffold

This folder contains cloud-oriented entrypoints for SUMO-RL training on the Quận 7/full-ROI target.
The package fixture in the example below is used only to validate the contract and CLI.

Use `rl_sumo_train.py` in dry-run mode first. It validates the district spec and reward profile
without training or writing model artifacts:

```powershell
uv run python scripts/training/rl_sumo_train.py `
  --spec tests/fixtures/specs/toy_public_district_v1.json `
  --scenario normal_weekday `
  --reward-profile configs/training/rl_reward_profile_v0.example.toml `
  --out-dir artifacts/tmp/rl_training_scaffold `
  --agent-mode multi_agent `
  --memory lstm `
  --dry-run
```

The real training entrypoint now supports:

- `--agent-mode multi_agent`: SUMO-RL PettingZoo parallel environment with one shared policy;
- `--memory lstm`: `sb3-contrib` RecurrentPPO;
- `--memory frame_stack`: a vector frame-stack baseline;
- `--memory none`: plain PPO baseline;
- `--num-envs`: optional SuperSuit parallel environment copies;
- `--rollout-steps`: per-agent rollout length before each PPO update.

Actual training is intended for Google Colab or Kaggle, with outputs written to Drive/Kaggle
working storage. The script refuses local training unless explicitly overridden. Start with one
multi-agent environment copy on the reviewed ROI before increasing `--num-envs`.

The reward profile, official flow calibration and hard constraints remain template-level. Economics
and CS should approve them before policy claims. Camera-partial-observation RL may begin with the
geometry-based optical visibility design; YOLO training is not a prerequisite.
