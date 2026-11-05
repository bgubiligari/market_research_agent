# Dashboard wireframe

Phase 1 low fidelity draft. Phase 4 implementation is in `apps/web`; this draft is not its final design.
Stockrow informs comparison structure; the UI adds sourced competitive research and charts.

## Setup

```text
Market Research Agent                         [Load HSY demo]
Target company        [Name / ticker / website                ]
Competitors           [Peer 1]  [Peer 2]  [Peer 3]
                      or [Discover competitors]
Optional scope        [Geography] [Research focus]
Recent news           [90 days]
                                           [Review research plan]
```

## Review and progress

Show resolved company identities, source websites, overlap explanations, and warnings. Allow
corrections before confirming the four-company plan. Progress shows overall stage and company
rows, warnings and cancellation. Reload/reconnect recovers the temporary run handle when valid.

## Results

```text
HSY vs MDLZ vs KHC vs GIS            [As of timestamp] [Coverage]

Executive briefing
Key differences, competitive pressures, opportunities   [Sources]

[Research] [Financials] [Recent developments] [Evidence]

Research              HSY          MDLZ         KHC          GIS
Products / brands     ...          ...          ...          ...
Positioning           ...          ...          ...          ...
Customers / geography ...          ...          ...          ...

Financials            [Fiscal period note and coverage warnings]
[Three-year annual revenue trend                         ]
[Latest revenue growth]     [Latest gross margin          ]
[Latest operating margin]   [Latest operating CF growth   ]
[Accessible underlying values table and source links     ]

Recent developments   [All companies v] [Date and source cards]
Evidence drawer       Source excerpt, publisher, period, URL
Limitations           Missing fields, conflicts, reporting dates
```

Stable company colors across all charts. No fabricated scores, dual axes or missing-as-zero.
Charts show exact periods, currency/scale, and provenance in tooltips and companion tables.
OCF growth with nonpositive prior OCF is marked not meaningful and shows underlying amounts
and absolute change. Fiscal-year labels do not imply a common calendar period. Different
currencies are not aggregated without an explicit conversion design (outside MVP1).

Stack charts on smaller screens. Let the four-company comparison scroll horizontally with
identities retained. Use accessible labels and data tables. Design loading, empty, partial,
cancelled, expired, source-failure and configuration-error views alongside the happy path.


## Implemented redesign

The Word UI proposal was reviewed and adapted to the approved local MVP. Current layout:
compact setup/scope sidebar; workflow + review panels during research; expanded briefing
canvas after completion. Report tabs: Overview, Companies, Comparison, Financials,
Recent developments, Sources. Latest five-metric matrix precedes charts and expandable
annual details. Claim/metric evidence opens in a modal side drawer. Mobile uses Setup,
Run, Briefing bottom navigation. The proposal's pricing, saved projects, accounts,
exports, confidence scores and mid-run interventions were not adopted.
