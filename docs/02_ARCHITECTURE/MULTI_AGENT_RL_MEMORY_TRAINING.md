# Multi-Agent RL with Temporal Memory

## Scope

The project target is a full Quận 7 SUMO network or a reviewed ROI containing roughly 100
signalized intersections. The small SUMO package fixture is retained only for CI and adapter smoke
tests; it is not the research-scale environment.

The control architecture should therefore use one shared policy across traffic-signal agents, with
local observations and optional neighborhood summaries. It must not create one independently tuned
PPO model per signal.

## Environment interface

SUMO-RL provides both Gymnasium and PettingZoo-compatible interfaces. The training entrypoint uses:

```text
SUMO-RL parallel_env
  -> SuperSuit PettingZoo-to-VecEnv adapter
  -> shared Stable-Baselines policy
  -> PPO or RecurrentPPO
```

The shared policy learns reusable signal-control behavior while each agent receives its own local
observation stream. Future graph message passing or centralized critics can replace the vector
adapter without changing the SUMO export, trace or reward contracts.

## Memory modes

The training script supports three template modes:

| Mode | Policy | Use |
|---|---|---|
| `none` | Stable-Baselines3 `PPO/MlpPolicy` | fully observed or memoryless baseline |
| `frame_stack` | PPO plus vector frame stack | cheap temporal baseline |
| `lstm` | `sb3-contrib` `RecurrentPPO/MlpLstmPolicy` | partial observation and temporal belief |

The current default is multi-agent with LSTM memory. This is an environment/training scaffold, not a
claim that the final observation contract or reward has been approved.

## Dependencies

The RL memory/multi-agent path uses:

- `stable-baselines3` for PPO and vector environments;
- `sb3-contrib` for `RecurrentPPO`;
- `pettingzoo` for the multi-agent API;
- `supersuit` for PettingZoo-to-SB3 vectorization;
- `sumo-rl` for the SUMO traffic-signal environment.

The current dependency range pins PettingZoo below 1.25 because SUMO-RL 1.4.5 still imports its
agent-selector symbol using the older callable shape. The training entrypoint also contains a small
compatibility shim and pads different intersection observation/action sizes before shared-policy
vectorization.

These are declared in `pyproject.toml` and `requirements-colab.txt`. SUMO itself remains an external
runtime and still requires `SUMO_HOME` plus the SUMO binaries.

## Training command

Dry-run validation remains safe and does not require a trained model:

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

For a real Quận 7/ROI run, use the district-specific spec or existing-net route workflow and train
in Colab/Kaggle/another approved runtime:

```powershell
uv run python scripts/training/rl_sumo_train.py `
  --spec <district-spec.json> `
  --scenario <scenario-id> `
  --reward-profile <approved-profile.toml> `
  --out-dir <cloud-output-dir> `
  --agent-mode multi_agent `
  --memory lstm `
  --num-envs 1 `
  --rollout-steps 128 `
  --train
```

`--rollout-steps` controls how many samples each vector agent collects before a PPO update. Keep
it modest while measuring CPU/memory use on the large ROI.

`--num-envs` is intentionally conservative by default. A large ROI can exhaust CPU, memory or SUMO
process capacity quickly; increase it only after one shared-policy run is stable.

## What remains template-level

The current reward profile is still a draft and the official project demand/flow calibration is not
complete. The script therefore keeps the existing reward callback and route export contracts rather
than inventing a new reward or synthetic flow model.

Before research claims, the team must implement or approve:

- the project observation adapter, including camera visibility fields;
- the official reward and hard safety constraints;
- policy evaluation on the full Quận 7/ROI network;
- fixed-time and rule-based baselines on the same scenarios and seeds;
- memory-state handling during evaluation and episode truncation;
- per-agent and network-level metrics.

## Scaling beyond the shared baseline

For approximately 100–160 signals, the next research steps are:

1. shared recurrent policy with fixed-size local observations;
2. neighborhood summaries or graph message passing;
3. centralized training with decentralized execution if coordination remains weak;
4. policy masks for upgraded/non-upgraded signals;
5. scenario and camera domain randomization.

The current scaffold is deliberately extensible toward these options but does not claim convergence
or production performance at that scale.
