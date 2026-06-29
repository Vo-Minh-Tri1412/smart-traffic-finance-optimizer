# Economics/Public Finance Team Guide

The Economics team does not need to code or understand RL internals. Its job is to make the simulated
district believable and to define what "public value" means when the city has limited budget.

For a plain Vietnamese explanation, start with
[Economics Plain-Language Guide](ECONOMICS_PLAIN_LANGUAGE_GUIDE.md).

## Main responsibilities

- Define which city zones matter: industrial zone, hospital, school, residential area, market,
  public administration, bus corridor, nightlife/event area.
- Define trips in plain language: who travels from where to where, at what time, and by what vehicle.
- Define scenarios: morning school/work rush, industrial shift, logistics peak, hospital emergency,
  market/nightlife spike, incident, and limited-budget rollout.
- Define which delays matter more: ambulance, bus passengers, workers, trucks, students, ordinary
  private vehicles.
- Define public-finance assumptions: installation cost, maintenance cost, value of time, fuel/emission
  proxy, logistics delay value, and caveats.
- Prepare judge-facing narrative and Q&A.

## Week-1 tasks

1. Fill the zone table:
   - zone name;
   - why it exists;
   - traffic it creates;
   - economic/social meaning.
2. Fill the trip table:
   - from where;
   - to where;
   - time window;
   - main vehicle types;
   - why the trip matters.
3. Fill the scenario table:
   - what happens;
   - which trips increase;
   - which places are affected;
   - what policy question the scenario answers.
4. Fill the priority/economic assumptions table:
   - which vehicle or trip should be weighted higher;
   - placeholder value or source;
   - caveat.
5. Draft Q&A:
   - Why simulation is useful?
   - Why not optimize every intersection?
   - Why are ambulance, bus, worker, and truck delays treated differently?
   - What are the limits of the result?

## Handoff to CS

Economics hands off tables, not code.

CS turns those tables into:

- demand flows;
- vehicle types;
- scenarios;
- metrics;
- public-finance scoring.

Economics should not fill the RL observation space. The canonical observation contract is
[Observation Space v1](../02_ARCHITECTURE/OBSERVATION_SPACE_V1.md), and it is owned by CS/system
architecture.

## Good evidence

Prefer sources from:

- government or public agencies;
- transport research papers;
- development banks or public policy reports;
- clearly stated team assumptions when no official number is available.

Every assumption must be marked as sourced, estimated, or placeholder.
