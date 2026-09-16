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
  --map-economic-profile <approved-map_economic_profile.v1.json> `
  --out-dir <cloud-output-dir> `
  --agent-mode multi_agent `
  --memory lstm `
  --num-envs 1 `
  --rollout-steps 128 `
  --train
```

When `--map-economic-profile` is supplied, the TOML reward profile continues to validate scenario
references and hard safety constraints, while the scalar passed to PPO comes from the map-economic
profile. The adapter resolves each observed vehicle through OD pair, building, zone, corridor, then
global fallback. It reads SUMO's cumulative `getTimeLoss()` but monetizes only the non-negative
increment since the preceding decision for that vehicle at that signal. A first sighting establishes
a baseline, so already accumulated delay is not charged again at every control step.

The economic evaluator produces two deliberately separate outputs:

- an auditable raw public-cost ledger in VND at the profile price year;
- a numerically scaled and clipped reward for PPO.

Training manifests record the economic profile ID/status, current coverage audit, reward mode, and
ledger scope. Each callback exposes its own sampled cost by signal; vectorized environment copies
own separate ledgers, so the manifest does not claim a complete network or training-run cost.
First-sighting and between-sample departing-vehicle delay is omitted by this shaping adapter.
Finance evaluation must use complete SUMO trip outcomes. Profile occupancy retains its evidence
and uncertainty rather than being overwritten by generic vehicle-class defaults. The profile's map
ID must match the training spec; the existing-net map still requires an explicit OD binding before
using this spec-export training entrypoint.
A failed production-coverage gate blocks `--train` by default. The explicit
`--allow-unreviewed-map-economics` escape hatch is for exploratory engineering only and does not
authorize a policy, causal-savings, or budget recommendation.

`--rollout-steps` controls how many samples each vector agent collects before a PPO update. Keep
it modest while measuring CPU/memory use on the large ROI.

`--num-envs` is intentionally conservative by default. A large ROI can exhaust CPU, memory or SUMO
process capacity quickly; increase it only after one shared-policy run is stable.

## What remains template-level

The repository now has a map-economic profile contract, deterministic coverage audit, incremental
reward evaluator, and SUMO-RL adapter. The checked-in District 7 seed configuration is still a draft:
its numeric values are labelled assumptions, the map boundary is unverified, and reviewed OD demand
is unavailable. The old technical reward remains available for compatibility, but it is not a
substitute for economic calibration.

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
