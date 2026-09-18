# Current ROI travel and OD source review

Reviewed 2026-09-16. This is a source-access and applicability review, not a calibrated demand
dataset. The user-selected ROI stays exactly `[106.690981, 10.692829, 106.788488, 10.779370]`
(west, south, east, north; longitude/latitude). Do not replace it with an administrative boundary.

The existing `district7_demand.v1.json` explicitly describes a 900-second synthetic policy scenario
with placeholder demand. The economic profile currently has structural mapping but no reviewed OD
denominator. Public sources below can support route supply, historical priors and a targeted data
request. None establishes current building-to-building trip volumes across this ROI.

## Verified source candidates

### TRAVEL-SAIGONBUS-038 and TRAVEL-SAIGONBUS-139

Primary operator pages expose directional street itineraries and service tables:

| Source | Verified published facts | Applicable use |
|---|---|---|
| [SaigonBus route 38](https://saigonbus.com.vn/cac-tuyen-xe/khu-dan-cu-tan-quy-ben-thanh-dam-sen/) | Tân Quy to Đầm Sen via the central area; table effective from 19 February 2024 lists 120 bus runs/day, 05:15-19:00, 47-place vehicle | Candidate transit service corridor through the prepared map; timetable prior after current-operation verification |
| [SaigonBus route 139](https://saigonbus.com.vn/cac-tuyen-xe/ben-xe-mien-tay-khu-tai-dinh-cu-phu-my/) | Miền Tây to Phú Mỹ; published itinerary includes Nguyễn Hữu Thọ, Nguyễn Thị Thập, Tân Mỹ, Nguyễn Lương Bằng, Huỳnh Tấn Phát; same effective date lists 120 runs/day and 10-20 minute headway | Candidate north-south/east-west transit exposure, including crossings of the ROI boundary |

Access: readable public HTML, verified through direct page opens. No downloadable GTFS/stop-coordinate
file or explicit open-data license was verified on these pages. Footer reserves rights. Store source
metadata and derived mapping decisions; confirm reuse terms before redistributing source content.
The 2024 effective date does not certify unchanged service in September 2026. Capacity is not actual
occupancy; scheduled bus runs are not passenger trips; a daily total does not reveal direction or
peak-hour distribution. These sources alone cannot populate `annual_trips` for a building OD.

### TRAVEL-JICA-SOUTHERN-APPENDIX

[JICA Southern Roads and Bridges appendix](https://openjicareport.jica.go.jp/pdf/12305017_02.pdf)
is a directly accessible 105-page PDF. Appendix 1, Tables 1.1.1-1.1.6 documents historical
HOUTRANS/METROS household travel surveys and zone-based generation/distribution. Surveys refer to
2002 and 2013, each approximately 20,000 households. Zones are wards or grouped wards, not buildings.
The overview and detailed zone-system descriptions use different counts; obtain the underlying
zone codebook before spatial joins. Table 1.1.10 (PDF page 17, printed Appendix 1-15) separates
PCU factors from vehicle occupancy and compares historical studies. PCU must never be substituted
for persons/trip. This supports model design and explicit historical sensitivity priors, not a
current local calibration. No machine-readable OD matrix, household microdata download or open
redistribution license was verified. PDF text extraction succeeded; web screenshot rendering failed,
so numeric table transcription is deferred to visual validation before ingestion.

### TRAVEL-JICA-HOUTRANS-FREIGHT

[HOUTRANS freight appendix](https://openjicareport.jica.go.jp/pdf/11764636_10.pdf), Table 3.1.1,
printed A3-1, identifies historical freight count/interview locations including Tân Thuận 1,
Tân Thuận 2, VICT and KCX Tân Thuận. The grain is a surveyed facility gate with 24-hour in/out
vehicle classes; later tables discuss OD interviews. This is a useful local sampling-frame lead,
not contemporary shipment demand. PDF is publicly addressable, but direct text extraction was
empty and screenshot rendering failed; the table was discoverable in indexed publisher content.
No numeric cells were imported, and no open redistribution license or raw interview data was
verified. Historical port activity and access gates require revalidation before transferring counts.

Local evidence makes this lead concrete: the current semantic overlay contains
`way_220688059_P1` through `P7`, all named Cảng Tân Thuận 2. These are seven geometry pieces
of one source way. Attaching the same facility count to all seven would multiply demand sevenfold.
Use a reviewed parent facility and its actual entrance gates before allocating traffic to pieces.

### TRAVEL-HCMC-TRAFFIC-PORTAL

The official [portal description](https://giaothong.hochiminhcity.gov.vn/About/) and
[user guide](https://giaothong.hochiminhcity.gov.vn/Userguide/) describe cameras, incidents,
traffic conditions and routing. This is an inspection/data-request lead. A portal timestamp or
colored traffic layer is not an observed OD matrix. The retrieved homepage also exposed an old
traffic-update timestamp alongside newer page timestamps, so freshness needs field-level checks.
No bulk count-history export, documented public API or camera calibration was verified.

Its [terms, intellectual-property section](https://giaothong.hochiminhcity.gov.vn/TermOfUse/)
allow limited personal viewing/download/printing and restrict reuse without written permission.
This is not an open training-data license. No camera images or streams were copied into the
project. An authorized export with defined reuse terms is the actionable route for quantitative
validation; requests have not been sent.

### Access gaps retained explicitly

- [HCMC data portal](https://data.hochiminhcity.gov.vn/) points to the public
  [open-data portal](https://opendata.hochiminhcity.gov.vn/). The latter returned a human-verification
  challenge in this session. No dataset catalog, license or download was verified; do not claim
  that suitable data does not exist. No challenge bypass was attempted.
- [Public transport authority route finder](https://buyttphcm.com.vn/RouteFinding) is indexed with
  authority attribution. Its homepage returned HTTP 403 when opened. Current route-specific data,
  GTFS and a bulk license remain unverified. Third-party copied timetables are not substituted as
  current official evidence.

## Concrete ingestion and calibration path

The following is proposed engineering work, not evidence already acquired:

1. Preserve the ROI, source-net hash and overlay hash. Create parent-facility IDs from source
   elements; review campuses/ports split into multiple polygons and identify entrance edges.
2. Create `transit_service_evidence` records for the two verified operator pages: source ID,
   accessed date, effective date, route number, direction, ordered street names, operating window,
   scheduled runs/day, vehicle capacity, license status and freshness status. Leave passenger
   volumes and actual occupancy null. Match itinerary streets to the existing SUMO net with a
   reviewed ordered edge sequence. Retain uncertain/ambiguous matches instead of shortest-path
   guesses labeled as observed routes.
3. Request/export the smallest necessary official tables: GTFS or stop coordinates plus ordered
   route geometry and service calendar; anonymous boardings/alightings by stop/direction/time bin;
   camera or loop counts by junction approach, movement, class and time; port-gate counts by class,
   direction and time; household-survey zone polygons, OD matrices, purpose/mode and expansion
   weights. Record survey date, sample coverage, missing intervals and reuse permission. Public
   pages above identify source owners; no external contact has been made.
4. Clip the representation to the exact ROI while retaining entry/exit connectors for trips whose
   true origin or destination is outside it. A clipped route endpoint is a boundary connector,
   not a fabricated local building. Whole-route ridership cannot be attributed entirely to its
   in-ROI segment.
5. Infer building allocations only after supplying reviewed population/jobs/enrollment/service
   capacity and entrance data. Use a constrained OD model that preserves observed zone totals and
   counts; mark every disaggregated building OD as estimated. Validate held-out counts, directions,
   travel times and time windows. Regional priors do not become local measurements through fitting.
6. Feed reviewed volumes and occupancy into `od_pairs`; keep historical/transferred inputs marked
   as assumptions where geographic or temporal transfer is unresolved. SUMO then measures signed
   marginal time loss per intervention and route. Only these deltas, multiplied by reviewed
   economic values, enter reward/QUBO. Annualization requires an explicit service/work calendar.

Required acceptance evidence: every ingested number has source location and year; no duplicate
facility demand across split polygons; no capacity-as-occupancy substitution; no city-level total
presented as building OD; no unreviewed cross-boundary route truncation; the production gate stays
failed while the reviewed demand denominator remains unavailable.
