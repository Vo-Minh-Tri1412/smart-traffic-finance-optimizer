# Economic source review for the retained ROI

Reviewed 2026-09-16. The user retained the existing map ROI. This research does not alter its
geometry or turn the ROI into an administrative district. Machine-readable provenance is in
`data/catalog/map_economic_sources.research.v1.json`; no calibration config was changed.

## Evidence that can be used

| Source and locator | Verified content | Status for this map |
|---|---|---|
| [JICA southern roads, Appendix 1-28, Table 1.2.9](https://openjicareport.jica.go.jp/pdf/12305017_02.pdf#page=30) | Historical income-derived passenger VOT; separate per-passenger and per-vehicle columns | Methodological prior; needs price transfer and OD calibration |
| [JICA, Appendix 1-29, Table 1.2.10](https://openjicareport.jica.go.jp/pdf/12305017_02.pdf#page=31) | Freight opportunity cost depends on commodity and loading | Supports differentiated logistics cost; does not establish ROI cargo mix |
| [World Bank PAD1305, Annex 6, p.72 and footnote 32](https://documents1.worldbank.org/curated/en/558961468179946764/pdf/PAD1305-PAD-P126507-IDA-R2015-0120-1-Box391444B-OUO-9.pdf#page=84) | VOT is a Hanoi proxy projected in a 2015 appraisal | Forecast 2025 is not observed 2025; retain only as sensitivity benchmark |
| [NSO VHLSS 2024, Table 5.7](https://www.nso.gov.vn/wp-content/uploads/2026/03/Sach-Khao-sat-muc-song-dan-cu-2024.pdf) | Indexed HCMC row reports mean 7,105.9 thousand VND/person/month | Provisional: direct PDF timed out; page/unit visual check remains |
| [NSO CPI 2025](https://www.nso.gov.vn/du-lieu-va-so-lieu-thong-ke/2026/01/chi-so-gia-tieu-dung-chi-so-gia-vang-va-chi-so-gia-do-la-my-thang-muoi-hai-quy-iv-va-nam-2025/) | National annual-average CPI rose 3.31% | General-price bridge 2024 to 2025 only; not a wage or commodity index |

JICA's income method uses METROS 2013 data, GDP-deflator transfer to 2016 and 22 x 8 work hours.
Its reported 2016 passenger-hour values are USD 1.58 for motorcycle users, 3.72 for car users,
and 1.16 for bus users. This is an appraisal derivation, not a building-level measurement.
Vehicle-hour values already incorporate occupancy; multiplying them by occupancy again would
double-count people. Cargo time cost is separate from driver/passenger time.

Household per-capita income includes children, non-workers and non-wage income. Dividing it by
working hours would not produce measured employee VOT. An inflation adjustment also does not
establish real wage growth or current willingness to pay. Keep original currency, price year,
deflator series, conversion formula and transfer uncertainty alongside any eventual prior.

## Source quality findings

The [new HCMC yearbook landing page](https://thongkehochiminh.nso.gov.vn/Blog/ChiTietAnPham/2705?slug=nien-giam-thong-ke-tp-hcm-2024)
contains explicit sample placeholder content. It is excluded from numerical evidence. The old
yearbook PDF could not be fetched, and the equivalent new-host path returned 404. The larger
JICA Line 3A document was not fully retrieved and contributes no extracted calibration here.

Primary PDF text for JICA and World Bank was read; PDF screenshot verification was attempted
but network retrieval was unreliable. NSO income and CPI results are explicitly marked as
official indexed extracts rather than fully reviewed local PDFs. These access limits are retained
in the registry instead of silently promoting entries to approved evidence.

## How this changes the map-specific reward design

The following is an implementation recommendation, not an observed economic result:

- Residential to employment: distinguish commute from on-duty business travel; use observed
  person counts and purpose, with time savings valued once.
- Industrial/port to warehouse or market: add marginal cargo inventory, spoilage or deadline
  costs only with commodity/load evidence; never count the entire shipment as a saved benefit.
- Residential to school or healthcare: track arrival deadlines, essential access and equity
  constraints alongside monetary time cost. Building tags alone do not justify arbitrary premiums.
- Commercial/service trips: model route-specific delay and reliability separately. Revenue or
  gross output at a destination is not automatically incremental public benefit from a faster trip.

Next calibration records need facility ID, directed OD, departure interval, purpose, route edges,
volume, occupancy, price year, and provenance. Split polygons belonging to one physical facility
must share a parent identifier before demand allocation. See the parallel
[travel source review](CURRENT_ROI_TRAVEL_SOURCE_REVIEW.md) for actual local route and facility leads.

Source discovery improves the evidence backlog; it does not yet raise the profile's source-backed
calibration coverage. Current operational reward remains explicitly assumption-based until the
transfer calculations and OD observations are reviewed.
