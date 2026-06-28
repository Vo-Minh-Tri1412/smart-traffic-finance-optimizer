# Economics/Public Finance Team Guide

The Economics team should not need to write code, but its work must enter the technical objective.
Economics is not only a presentation layer.

## Main responsibilities

- Define public-finance assumptions.
- Define traffic and budget scenarios.
- Explain why reduced delay matters for public spending.
- Define the public-value formula used by CS in scoring.
- Define budget constraints and sensitivity ranges.
- Prepare judge-facing narrative and Q&A.

## Week-1 tasks

1. Fill the public-finance assumptions sheet:
   - value of time
   - fuel/emission proxy, if used
   - implementation cost assumption
   - operating or maintenance cost assumption
   - fairness/service-level caveat
   - caveat for each assumption
2. Fill the scenario sheet:
   - rush-hour scenario
   - event or incident scenario
   - limited-budget deployment scenario
3. Write Q&A:
   - Why use RL?
   - Why simulation is still useful?
   - What are the limits of the result?
   - How does this support public finance?

## Required technical handoff to CS

Economics must hand off a scoring contract that CS can implement:

```text
public_value_score
  = delay_saved_minutes * value_of_time
  + optional fuel_or_emission_proxy
  - implementation_cost
  - operating_or_maintenance_cost
  - fairness_or_service_penalty
```

For every term, mark whether it is sourced, estimated, or placeholder. If a term is too weak for
Week 1, keep it in the formula but set it to `TBD` or `0` with a caveat instead of pretending it is
known.

## Good evidence

Prefer sources from:

- government or public agencies
- transport research papers
- development banks or public policy reports
- clearly stated team assumptions when no official number is available

Every assumption must be marked as sourced, estimated, or placeholder.
