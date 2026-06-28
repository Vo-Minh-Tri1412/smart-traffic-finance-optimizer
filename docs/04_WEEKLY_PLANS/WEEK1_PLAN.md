# Week 1 Plan: SUMO-RL Traffic Public Finance Reset

Week: 2026-06-29 to 2026-07-05

## Top outcomes

1. CS environment can report SUMO/SUMO-RL readiness.
2. Economics has traffic/public-finance assumptions and scenarios ready for CS.
3. The team can explain why the project belongs to public finance, not only smart traffic.

## CS deadlines

| Due date | Deliverable | Definition of done |
| --- | --- | --- |
| 2026-06-29 | SUMO runtime checklist | `doctor` reports Python packages and clearly warns if SUMO binary is missing. |
| 2026-07-01 | SUMO-RL technical path | Documented sample env target, state/action/reward draft, and baseline plan. |
| 2026-07-03 | Baseline metric schema | Fixed-time/rule-based metrics defined before RL claims. |
| 2026-07-05 | CS handoff v0 | Short report for Economics: assumptions, outputs, caveats, questions. |

## Economics deadlines

| Due date | Deliverable | Definition of done |
| --- | --- | --- |
| 2026-06-30 | Public-finance assumptions v0 | Value-of-time, cost categories, and caveats filled in Drive template. |
| 2026-07-02 | Traffic policy scenarios v0 | At least 3 traffic/budget scenarios with expected direction and confidence. |
| 2026-07-04 | Narrative and Q&A v0 | Why this is public finance, what RL optimizes, and what simulation cannot prove. |
| 2026-07-05 | Joint review | CS and Economics agree on Week-2 priorities. |

## Week-1 rule

Do not start with a custom simulator. Use SUMO-RL as the official target. If SUMO is not installed
yet, document the blocker and continue with architecture, metrics, and templates.
