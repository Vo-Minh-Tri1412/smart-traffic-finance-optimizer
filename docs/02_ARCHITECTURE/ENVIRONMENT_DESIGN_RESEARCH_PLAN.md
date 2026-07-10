# Environment Design Research Plan

This document plans how the team will design a realistic SUMO/SUMO-RL environment for
**Smart Traffic Public Finance Optimization**. It is intentionally a planning artifact only:
no SUMO network files, no route files, no RL training, and no custom simulator are introduced here.

The target is the full Quận 7 OSM/SUMO district or a reviewed ROI of roughly 100 signalized
intersections. It must feel like a project, not a tutorial map: hospitals,
schools, residential zones, offices, entertainment/nightlife demand, priority vehicles, road capacity
differences, bottlenecks, and candidate intersections for public investment decisions.

## Non-goals for this step

- Do not create `.net.xml`, `.rou.xml`, `.sumocfg`, or generated SUMO artifacts.
- Do not train RL agents.
- Do not choose final reward weights.
- Do not replace the reviewed Quận 7/ROI source with an unrelated sample map.
- Do not build a custom traffic simulator outside SUMO/SUMO-RL.

## Evidence checklist

| Claim | Source | What the source supports | Caveat | Apply now? |
|---|---|---|---|---|
| SUMO can model signalized intersections with explicit traffic light phases/programs. | [SUMO Traffic Lights](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html) | Traffic lights are a first-class SUMO object and can be represented with controlled phases. | This does not design our district or reward function by itself. | Yes |
| SUMO can define vehicle types, vehicles, trips, routes, and route distributions. | [SUMO vehicle and route definitions](https://sumo.dlr.de/docs/Definition_of_Vehicles%2C_Vehicle_Types%2C_and_Routes.html) | Demand can be represented through vehicle types and explicit trips/routes. | Realistic calibration still needs scenario assumptions or real counts. | Yes |
| SUMO has demand-generation tooling and route workflows. | [SUMO Demand](https://sumo.dlr.de/docs/Demand/) | Demand can be generated or specified through multiple supported workflows. | Tooling choice depends on final map and desired realism. | Yes |
| SUMO can import OpenStreetMap networks. | [SUMO OpenStreetMap import](https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html) | A real district map is possible in principle. | OSM import requires reviewed cleanup and demand calibration. | Yes: Quận 7/ROI |
| SUMO-RL supports Gymnasium and PettingZoo interfaces for traffic signal control. | [SUMO-RL documentation](https://lucasalegre.github.io/sumo-rl/) | The main RL interface can be multi-agent and can support custom observation/reward logic. | The library interface does not make the project unique; our environment and public-finance framing must. | Yes |
| A SUMO modeling workflow should separate network, demand, control, simulation, and evaluation. | [Traffic Modeling with SUMO tutorial](https://arxiv.org/html/2304.05982v2) | Provides a useful workflow lens for structuring the simulation design. | Tutorial-level evidence; final design still needs team-specific choices. | Yes |

## Research workstreams

### 1. Network design

Research and decide how the district should represent:

- arterial roads versus local roads;
- lane counts, speed limits, and road capacity differences;
- signalized and unsignalized intersections;
- intentional bottlenecks;
- queue formation and spillback risk;
- traffic light programs for fixed-time and rule-based baselines;
- candidate intersections that could receive public investment.

Output of this workstream: a map concept with labeled roads, candidate intersections, bottlenecks,
and a first list of SUMO features required to implement it later.

### 2. Demand design

Research and decide where vehicles start, where they go, and when demand changes:

- morning residential-to-school/office flows;
- afternoon school/office-to-residential flows;
- evening entertainment/quán nhậu flows;
- hospital-related priority trips;
- bus or public-service routes;
- special events, incidents, or one-off spikes;
- vehicle type mix: private cars, buses, ambulances, taxis/ride-hailing, and optional light trucks.

Output of this workstream: a demand matrix concept, not route files yet.

### 3. Semantic city layer

Design a district with social meaning, not just a grid:

- hospital zone;
- school zone;
- residential zone;
- office/public administration zone;
- entertainment/quán nhậu zone;
- bus stop, bus corridor, or priority route;
- commercial/event zone;
- optional logistics/service zone.

Each location must answer: why does it exist, what traffic pattern does it create, and how does it
connect to public-finance decisions?

### 4. Control and evaluation layer

Plan controllers and metrics before implementation:

- fixed-time controller as the simple baseline;
- rule-based controller as a stronger non-RL baseline;
- shared multi-agent RL controller for the reviewed signalized ROI, with an upgrade mask for
  intersections that are not equipped;
- RL observation must follow [Observation Space v1](OBSERVATION_SPACE_V1.md), not a separate
  document-specific list;
- fixed/rule-based control for less important intersections;
- comparison across waiting time, queue length, throughput, stopped vehicles, emergency delay, and
  per-intersection delay;
- translation from traffic metrics into public-finance signals, such as which intersections deserve
  investment first.

This layer must avoid pretending the RL agent directly solves public budgeting. The RL agent optimizes
traffic control; the public-finance layer uses measured improvements, costs, and policy priorities to
support investment decisions.

## Environment options

| Option | Strength | Risk | Best use |
|---|---|---|---|
| Full Quận 7 OSM/SUMO district | Highest geographic credibility and realistic network interactions. | Large-map demand, signal and render QA are expensive. | Current strategic target. |
| Reviewed Quận 7/ROI | Keeps the real network while bounding compute/render scope. | Boundary and demand calibration must be documented. | Current implementation target, roughly 100 signals where available. |
| Synthetic fixture | Deterministic and fast. | Not representative of the project network. | CI, adapter and dependency smoke tests only. |

Recommended implementation path: **reviewed Quận 7/ROI on the same SUMO source**. The demo should not
use a sample library map as the main project. The package fixture is acceptable only for smoke tests.

## Selection rubric

Use this rubric before approving the final environment design:

| Criterion | Good sign | Bad sign |
|---|---|---|
| Project credibility | The map looks like a small district with public services and policy tradeoffs. | It looks like a tutorial grid with renamed nodes. |
| SUMO feasibility | Intersections, lanes, routes, and signals can be represented without fragile hacks. | The design depends on unsupported simulator behavior. |
| Debug risk | A smaller version can run first, then expand. | The first working version requires a huge city map. |
| Public-finance link | Candidate investments and budget limits are visible in the design. | Finance appears only in the slide deck, not in the simulation outputs. |
| Evaluation clarity | Scenario -> metric -> policy use is explicit. | Metrics are collected without a decision they inform. |
| Extensibility | More zones/intersections can be added without rewriting the pipeline. | Expanding the map requires throwing away the design. |

## Environment Design Spec template

The next design artifact should fill this template.

### Map concept

- Full Quận 7 network or a reviewed ROI with approximately 100 signalized intersections when the
  source map supports it.
- Semantic zones and corridors are attached through the overlay, not hand-authored as a replacement
  for SUMO geometry.
- Main arterial roads with higher capacity.
- Local roads with lower capacity.
- At least one deliberate bottleneck.
- At least one hospital priority route.
- Candidate intersections for upgrades or signal-intelligence investment.
- Shared multi-agent RL can run across the ROI; an upgrade mask determines which signals receive
  intelligent sensing/control while others remain fixed-time or rule-based.

### Required places

| Place | Traffic role | Public-finance role |
|---|---|---|
| Hospital | Generates priority ambulance routes and delay-sensitive trips. | Supports equity and emergency-response metrics. |
| School | Creates morning and afternoon peaks. | Supports social-service and congestion-priority arguments. |
| Residential zone | Main origin in morning and destination in evening. | Represents citizen welfare and daily commute burden. |
| Office/public administration zone | Main work destination. | Represents productivity and public-service access. |
| Entertainment/quán nhậu zone | Creates evening demand spike and irregular return flows. | Supports scenario planning and safety/crowding discussion. |
| Bus corridor or priority route | Adds public transport or public-service tradeoffs. | Allows comparison between private-vehicle throughput and public-service priority. |
| Commercial/event zone | Creates optional event-driven demand spikes. | Supports stress-test and limited-budget decisions. |

### Vehicle types

- Private car.
- Bus.
- Ambulance or emergency vehicle.
- Taxi/ride-hailing.
- Optional light truck for service/logistics trips.

### Demand behavior

| Time/scenario | Main flow | Design implication |
|---|---|---|
| Normal weekday | Balanced trips across zones. | Baseline comparison. |
| Morning rush | Residential -> school/office. | Tests commute pressure and school-zone bottlenecks. |
| Afternoon/evening rush | School/office -> residential. | Tests reverse-direction congestion. |
| Evening entertainment spike | Residential/office <-> entertainment/quán nhậu zone. | Tests unusual demand not captured by simple commute logic. |
| Hospital priority | Emergency route crosses congested corridors. | Tests whether the controller protects critical trips. |
| Event/incident | One zone or road receives abnormal demand or capacity loss. | Tests robustness and scenario planning. |

### Road capacity rules

- Every road class must define lane count, speed, and intended capacity tier.
- Main roads should have higher capacity but can still become bottlenecks at key intersections.
- Local roads should have lower capacity and should not absorb unlimited traffic.
- The design should allow queues and spillback risk instead of assuming vehicles can always enter.
- At least one bottleneck must be explainable from the map, not invented after metrics are observed.

### Control scope

- Full district may contain many signalized intersections.
- Shared multi-agent RL can cover the reviewed ROI; an upgrade mask determines which signals receive
  intelligent sensing/control while other signals remain fixed-time or rule-based.
- This is a feature, not a weakness: it reflects public-budget limits where not every intersection can
  receive sensors, upgrades, or intelligent control at once.

## Scenario and metric planning

| Scenario | Purpose | Demand/control change | Required metrics | Public-finance use |
|---|---|---|---|---|
| Normal weekday | Establish baseline performance. | Standard demand across all zones. | Waiting time, queue length, throughput, stopped vehicles. | Baseline for investment impact. |
| Morning school/work rush | Stress commute and school access. | Increase residential -> school/office flows. | Average waiting time, per-intersection delay, queue length. | Identify commute-critical and school-critical bottlenecks. |
| Evening entertainment spike | Represent irregular nightlife/quán nhậu demand. | Increase flows to/from entertainment zone. | Queue length, stopped vehicles, per-intersection delay. | Show why static timing can fail under local events. |
| Hospital emergency priority | Protect delay-sensitive emergency trips. | Add ambulance trips through congested corridors. | Emergency vehicle delay, route travel time, affected queue length. | Evaluate whether investment improves critical public services. |
| Limited budget rollout | Choose only a few intersections to upgrade/control. | Compare candidate intersection subsets. | Benefit per intersection, delay reduction, cost placeholder. | Rank investment candidates under budget constraint. |
| Optional incident/event | Test robustness. | Reduce capacity on one road or spike one event zone. | Throughput, spillback proxy, total waiting time. | Stress-test resilience and contingency planning. |

Minimum metrics:

- total waiting time;
- average waiting time;
- queue length;
- throughput;
- stopped vehicles;
- emergency vehicle delay;
- per-intersection delay;
- candidate investment score input.

## Mapping to public finance

The traffic simulation should produce evidence for a public-finance decision:

```text
scenario -> traffic metric change -> candidate intersection benefit -> cost/priority assumption -> investment ranking
```

Example policy question:

> If the city can fund intelligent control or signal upgrades at only a budget-feasible subset of the
> Quận 7/ROI signals, which subset should be prioritized, and why?

The answer should combine:

- measured improvement from simulation;
- cost placeholder or sourced cost assumption;
- social priority, such as hospital delay or school-zone congestion;
- caveats about synthetic demand and missing real calibration.

## Review gates before implementation

The environment design is not ready for code until it passes all checks:

- It no longer looks like a sample/tutorial map.
- Every major place has a reason to exist.
- At least one bottleneck is visible on the map concept.
- At least one hospital/emergency priority route exists.
- At least one special demand generator exists, such as school, quán nhậu/entertainment, or event zone.
- Main and local roads have different capacities.
- Candidate intersections for investment are listed.
- Scenario -> metric -> public-finance use is explicit.
- The package fixture is clearly labeled as a smoke test and is not used as evidence for the
  Quận 7/ROI research claim.

## Role split for the next step

| Role | Responsibility |
|---|---|
| Team lead/integrator | Approves scope, keeps the environment from becoming too large too early. |
| CS | Checks SUMO/SUMO-RL feasibility, later implements map/demand/controllers only after spec approval. |
| Economics | Defines public-service zones, scenario logic, public-finance assumptions, and narrative caveats. |
| Reviewer | Confirms the design is not merely a tutorial grid and that metrics support policy decisions. |

## Next artifact after approval

When the user says to continue, create an **Environment Design Spec**. That spec should describe one
selected district design in detail. Implementation tasks for SUMO network files, demand generation, and
controllers should come only after that design spec is reviewed.
