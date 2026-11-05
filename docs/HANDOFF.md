# Current implementation handoff

Updated November 4, 2026. Workspace: `/Users/balaji/Documents/Projects/market_research_agent`.

## Requirements and user intent

Implement reviewed Project 3A architecture 1.1, preserving configurable company inputs
and HSY versus MDLZ, KHC, GIS as the first demo. Pricing is not required and should not be searched by default: the user explicitly noted
that these companies sell unlike products. Required qualitative fields are products/brands,
differentiators, customers, positioning, geography and recent developments.
Five metrics: reported revenue/net sales,
revenue growth, gross margin, operating margin and operating cash flow growth. Python
computes financials using official annual evidence. No delegation. No accounts, saved
report library, monitoring or deployment. Next.js UI is implemented in Phase 4; Phase 5 validation/submission is next.

Read AGENTS.md, this file, docs/architecture.md and docs/implementation-plan.md first.
The reviewed Word baseline remains `docs/market_research_agent_architecture_v1_1.docx`.
Root `.env` is configured; explicitly load with `uv run --env-file .env`. Never print keys.
Small bounded live validation calls were authorized; keep paid calls out of default tests.

## Repository checkpoint November 4 2026

The user requested committing the project to GitHub. Created the private repository
`https://github.com/bgubiligari/market_research_agent` for the initial main-branch source
snapshot. A pre-commit scan of all 64 candidate files (including Word XML) found no
configured credential values or token/private-key patterns. Root `.env`, local
virtual environments, node_modules, Next build output, browser artifacts and caches
are excluded. No new provider calls or application changes are part of this checkpoint.
Prior validation remains recorded below; tests are not claimed as rerun for publishing.

## Latest checkpoint: approved workspace redesign

The user reviewed `multi_agent_market_research_ui_design.docx` and approved the proposed
adaptation. The supplied document is a design reference, not authorization to add its
out-of-scope features. Implemented the agreed workspace/report redesign plus structured
company progress. No delegation and no new paid research calls in this redesign.

Actual changes:
- Compact header and persistent setup/scope sidebar. Setup, Run and Briefing views replace
  the long stacked page. Pipeline/review panels occupy the research canvas; reports expand
  across it. Mobile has sequential bottom navigation. The large marketing headline is gone.
- Dedicated identity/website review with exact-version approval; cancel/new request still
  changes scope. New requests prefill the resolved plan after cancel/retry, including after
  reload. Cancelling remains visibly cancelled; retained evidence opens only on selection.
- Report sections: Overview, Companies, Comparison, Financials, Recent developments,
  Sources. Existing cited positioning is grouped by company; no new unsourced executive
  synthesis. Six research dimensions align in a four-company comparison matrix.
- Financials starts with a five-row latest-year comparison. Historical charts remain
  selectable; the 60-value annual table is expandable. Clicking values opens exact metric,
  calculation breakdown and filing inputs. Decimal strings, negative values, currency
  separation, differing fiscal dates and not-meaningful explanations are preserved.
- Source citations and library cards open a native modal side drawer with publication/
  retrieval dates, stored excerpts, original URL and copy-citation control. Escape closes
  it and focus returns to the trigger. Search/company/type/cited-only filters reduce source
  clutter. Collected-source counts are distinguished from citations, not called confidence.
- Coverage summary exposes unsupported fields by company; detailed comparability warnings
  collapse below report content. Inferred basis remains attached to claim details.
- Backend snapshots add optional `company_progress` and a bounded 40-record `activity`
  history. Header-authorized `company_progress` SSE uses the existing replay sequence.
  Real branch stages include financial coverage, collection, analysis and follow-up;
  counts are reserved search attempts, collected sources and supported fields. Completion
  is determined from required coverage; branch failures are explicit. Late/terminal/cancelled
  events are discarded. No raw queries, prompts, upstream errors or reasoning are exposed.
- New components: `progress`, `financial-panel`, `evidence-drawer`, `icon`; reusable metric
  formatting in `lib/presentation.ts`. Request/plan/report contracts and backend credentials
  remain unchanged. Only the temporary handle is persisted in sessionStorage.

Final checks: **78 Python tests, 5 frontend unit tests, 7 production browser tests passed**;
TypeScript, production webpack build, schema export and compileall passed. Browser suite
finished in 18.4 seconds. The layout-specific browser check recorded no page errors.

Validation for this revision is recorded in `docs/validation/phase4-redesign-summary.json`.
Type/build, offline Python/frontend checks and browser checks against production Next.js
and external offline Uvicorn were exercised. Screenshots cover desktop setup/review,
report overview/financials, and 390px mobile. Browser examples explicitly say OFFLINE TEST.
No new real-provider run is claimed: the older live Phase 4 summary remains historical.

The full seven-test browser run found a cancellation navigation race; fixed auto-navigation
so only completed/partial runs automatically open Briefing. A screenshot taken before
hydration also initially triggered a Playwright caret-style hydration mismatch in development;
checks now wait for readiness and preserve caret styling. Final production checks supersede
those initial failures. Details and final counts are in the durable summary below.

## Current next steps after redesign

1. Phase 5 validation/submission remains next: reproducible setup, cited sample output,
   recording script and final review. No additional paid run is needed to establish layout.
2. Real provider evidence remains the earlier partial report: 60 available metrics and
   23/24 required qualitative fields, with KHC customers missing in that measured run.
   Coverage varies; do not imply a complete live report or invent missing news/customers.
3. New company telemetry is exercised with real API/graph orchestration and offline
   provider replacements over external Uvicorn. No new paid validation of the telemetry
   path is claimed. Chrome desktop/mobile-width checks are not a physical-device or full
   accessibility audit. Discovery/non-demo live identity coverage remains unverified.
4. Per-agent retry/source exclusion, mid-run scope edits, autocomplete, source preference
   switches, generative risks/opportunities, user edits, dark mode, shortcuts, saved
   projects, accounts, exports and pricing remain deferred. No confidence scoring added.
5. One localhost worker only. Restart clears temporary handles/reports; paused/terminal
   runs expire after 60 minutes. Cancellation cannot undo dispatched provider costs.
   See README for real and offline startup commands. Do not point browser tests to real
   providers; they require the offline readiness marker before creating runs.

## Previous checkpoint: initial Phase 4 frontend

Implemented `apps/web` with Next.js 16.4.3 / React 19 / TypeScript / Tailwind 4,
Recharts and a shadcn-style Radix/CVA button. Dependency versions are locked in
`apps/web/package-lock.json`. Local design is named Fieldnote. No accounts, report
library, monitoring or deployment were added. Read README's Phase 4 section for commands.

Actual behavior:
- Configurable target/three peers or discovery, HSY demo, optional geography/focus and
  news lookback. Readiness check blocks creation when backend configuration is missing.
- Resolved company/website/CIK review and exact-version human approval. Replacement uses
  explicit cancel/new request. Warns about imperfect overlap and fiscal differences.
- Same-origin fixed-origin Next Route Handler forwards REST and unbuffered fetch SSE.
  Run token stays in headers. Only temporary `{run_id,run_token}` is saved in sessionStorage;
  report, inputs, cursor and budget are not persisted. Reload fetches snapshot and replays
  from zero. In-memory Last-Event-ID supports reconnect; stale replay cannot regress a newer
  snapshot. Finite REST timeout, heartbeat silence detection, bounded reconnect backoff.
- Explicit cancel, expired/unavailable handles, capacity/configuration/failure/retry states;
  retained cancelled results display as partial evidence. Progress uses real overall API
  stages, not invented per-company percentages or completion events.
- Completed/partial reports, briefing, research, dated developments, all five selectable
  financial charts, accessible 60-row table for the demo, exact fiscal periods, filing
  inputs and source excerpts. Decimal strings are explicitly parsed, negative values
  retained, missing/not-meaningful values stay null, currencies chart separately. Breakdown
  amounts and reasons remain visible. Source text is escaped and URL protocols restricted.

Checks actually completed October 31, 2026:
- `uv sync --group dev --no-editable`, `uv run pytest`: **76 passed**.
- `uv run python scripts/export_contracts.py`: passed.
- `npm --prefix apps/web run typecheck`: passed.
- `npm --prefix apps/web test`: **4 passed**, covering Decimal parsing, safe links,
  chunked/CRLF SSE framing, missing/negative/not-meaningful/mixed-currency chart behavior.
- `npm --prefix apps/web run build`: passed with webpack, including TypeScript and static
  page generation. Turbopack failed on worker port binding in this environment, even after
  escalation; build command explicitly uses supported webpack. No deployment performed.
- **6 Playwright Chrome tests passed** against external offline Uvicorn + Next, exercising
  complete/partial reports, approval barrier, reload, cancellation before/during research,
  dropped SSE connection and replay cursor, expiry, unknown handles, capacity/configuration
  recovery, citations/financial table and 390px layout. Final regression uses production build.
  Harness reports explicitly say OFFLINE TEST; tests refuse to create a run without its
  readiness marker. Test-only controls are absent from the production backend.
- One bounded paid run used **Chrome → production Next.js → external Uvicorn → actual
  LangGraph/SEC/Nebius/Tavily**, root `.env` explicitly loaded by backend only. No fixture
  supplied. **Partial**, 45.38 seconds overall / 33.799 seconds after approval through UI
  checks, **60/60 financial values available**, **23/24 required qualitative fields**,
  78 sources. **KHC customers** was missing in this run; do not assume the earlier KHC
  recent-developments gap is fixed deterministically. Browser recorded zero page errors,
  header-token SSE connections with replay cursor 5, review reload and terminal reload.
  This run checks availability/rendering, not a new independent financial reconciliation.

Durable live summary: `docs/validation/phase4-browser-live-summary.json`. Temporary inspected
screenshot: `/tmp/project3a-phase4-live-financials.png`. Paid validation is isolated in
`scripts/check_browser_live.mjs --paid`. No credentials, run tokens, full prompts or logs
were written into the summary or handoff. No further paid runs are needed for Phase 4.

## Initial Phase 4 limitations (see latest redesign checkpoint above)

1. Phase 4 is implemented and verified. Start Phase 5: consolidate submission setup,
   cited sample output and recording script; choose whether another final measured demo
   adds evidence before spending on it. Existing real reports are partial; a complete
   report has only deterministic offline browser evidence.
2. Qualitative coverage varies by run. Keep unsupported fields explicit. Lexical quote
   matching does not independently prove entailment; human source review is still needed.
   Discovery/non-demo identity and generic financial concept mappings have not had a live
   browser/provider check. Demo is the only independently reconciled company set.
3. API publishes overall progress only. Company-specific progress events would require
   a backend contract change; the UI accurately describes up-to-two concurrent branches.
4. Browser automation is Chrome only. Mobile-width layout is checked, not a physical
   mobile device. API restart is represented by unknown-handle recovery; expiry uses an
   offline-only test control. No full OS/browser-matrix or independent accessibility audit.
5. One localhost API worker; reports/checkpoints vanish on restart, paused/terminal expiry
   is 60 minutes. No persistence, hosting or authentication. Cancellation cannot undo costs
   of already-dispatched synchronous requests. Budgets are reservations, not billing caps.
6. To run: root `PYTHONPATH=apps/api/src uv run --env-file .env uvicorn market_research.api:app
   --host 127.0.0.1 --port 8000 --workers 1 --no-access-log`; in another terminal use
   `npm ci --prefix apps/web` then `npm --prefix apps/web run dev -- --port 3002`.
   Open localhost:3002. Never load backend credentials into frontend env. Offline browser
   checks need `API_ORIGIN=http://127.0.0.1:8001` and the separate validation harness; stop
   that frontend and restart against default :8000 afterward. README has full commands.

## Historical Phase 3 checkpoint: targeted retrieval and scope change

The user asked to improve missing-field retrieval, then explicitly removed pricing from
required coverage because the companies sell unlike products. The required set is now
six fields per company (24 total). Default searches, analysis, missing-field generation
and report completeness exclude pricing. All five financial metrics are unchanged.

Implemented `evidence.py` with targeted portfolio/strategy, customers/geography and dated
news queries; representative literal windows per field; ISO/date-only/RFC publication
parsing; labeled page-publication parsing; focused follow-up queries. Extraction preserves
search dates, titles and provenance alongside relevant extracted content. Old/future news
is excluded before context selection and claim acceptance. Follow-up analysis sees only
unresolved fields and never erases successful earlier findings. Fixed company budget
shares after identity resolution prevent early branches from consuming later branches'
allowances. Shares and global budgets are both checked atomically before dispatch/retries.

Tavily requests publication metadata and explicit start/end date filters. A live validation
failure showed `days` cannot be combined with start/end dates; removed `days` from the
provider payload. A separate small live probe passed with five dated news results after
that fix. Local date/quote validation remains necessary even when upstream filters succeed.

Latest live four-company run: **partial, 38.67 seconds, 23/24 supported required fields**.
HSY, MDLZ and GIS each covered all six fields. **KHC recent developments** remains missing;
no valid claim was accepted in that run. All **60/60 financial metrics** were available
and matched reviewed expectations. 79 sources. Reserved 19 searches, 15 extracted URLs,
34 estimated Tavily credits, 11 model calls, 44,955 input and 9,424 output tokens; provider
reported 8,239 prompt and 2,850 completion tokens. No fixtures supplied to live research.
This is a single measured run, not guaranteed future coverage or independent entailment.

Durable summary: `docs/validation/phase3-retrieval-summary.json`. Full temporary result:
`/tmp/project3a-live-no-pricing.json`. Earlier 11-field and 8-field missing counts used a
seven-field scope including pricing and should not be compared without adjusting scope.
Two earlier bounded runs during this follow-up returned 18/28 and 20/28 supported fields,
revealing date filtering/context/budget issues fixed before the final run. Pricing was
removed only after the user's later instruction. No further paid runs are needed now.

Latest checks: `uv sync --group dev --no-editable` passed; `uv run pytest` **76 passed**;
schema export and compileall passed. The last small requested-field guard was also checked
with `.venv/bin/python -m pytest` (76 passed). Credentials were explicitly loaded with
`uv run --env-file .env` for live checks and never printed/copied. Next: Phase 4 UI, with
explicit partial coverage, safe evidence rendering and browser/SSE validation. KHC recent
news remains an evidence-quality follow-up; do not fill it with stale or invented news.

## Actual Phase 2 exit evidence

- Existing provider capabilities passed live for Nebius
  `Qwen/Qwen3-235B-A22B-Instruct-2507` (tool calling and structured output) and Tavily
  search/extract. These were separate capability probes, not combined tools/schema streaming.
- Fixed KHC revenue with a CIK-scoped `RevenueFromContractWithCustomerIncludingAssessedTax`
  mapping. This is the machine-readable tag for **reported consolidated Net sales**,
  not an instruction to add taxes or calculate alternative revenue. Verified against
  KHC 2025 10-K p.51. Display revenue as reported net sales/revenue; technical tags belong
  in evidence details. Other companies do not inherit this mapping.
- Reconciled three annual periods of all five metrics for each demo company (60 values).
  Reviewed official 2025/2024 annual filings for HSY, MDLZ, KHC and 2026/2025 for GIS.
  The older filing supplies fourth-year revenue and OCF growth denominators. Compact
  statement inputs, exact fact metadata, filing links, expectations and scope notes:
  `tests/fixtures/reconciled_financials.json`. Tolerance 0.000001 percentage points;
  revenue is base USD. GIS gross profit is derived from matching net sales/cost of sales.
- KHC negative 2025 GAAP operating income is retained. GIS FY2026 has 53 weeks; fiscal
  periods differ. Acquisitions/divestitures, impairment and presentation changes affect
  comparability; results are reported, never organic/adjusted. Filing HTML was read
  through web retrieval; direct archive HTTP returned 403.
- Public SEC demo retrieval passed for all companies. `/tmp/demo-financials.json` is
  the older unreconciled retrieval, not the source of truth. Corrected retrieval is
  `/tmp/demo-financials-fixed.json`; reviewed fixture is durable regression evidence.
- Phase 2 checkpoint: 44 offline tests, sync and contract export passed before Phase 3.

## Phase 3 implementation

- `api.py`: FastAPI lifespan/client cleanup, in-process task registry, opaque handles,
  header tokens, idempotency conflict checks, one active run, safe health/readiness,
  atomic plan confirmation, repeatable cancellation, report snapshots and fetch SSE.
  Monotonic event IDs, replay, snapshot fallback and heartbeats; SSE disconnect does
  not cancel work. Paused/terminal expiry 60 minutes, five-minute tombstones, 64-handle cap.
- `workflow.py`: actual LangGraph JSON-safe in-memory checkpoints and human interrupt;
  resolve → approval → two concurrent company branches → validation → deterministic
  cited briefing/report compilation. Branch failures preserve other companies. Snapshot
  report contracts check evidence ownership and financial input references.
- `research.py`: configurable supplied/discovered companies, SEC ticker identity when
  available, evidence-backed website selection, model query planning, Tavily general/news
  search and extraction, structured cited analysis and one coverage follow-up per company.
  Exact supporting quotes must occur in owned stored excerpts. Claims remain labeled
  inferred because lexical matching does not independently establish entailment. Missing
  fields are explicit. Recent findings require publication timestamps within requested
  lookback. No model arithmetic is used. Financials and excerpts are retained incrementally.
- `runtime.py`: reserve budgets before dispatch/retry, ten active minutes excluding review,
  finite retries and one structured-output repeat, Retry-After support (waits above 30 sec
  are refused), safe failures, output reservations and conservative UTF-8 input bounds.
  Actual numeric model usage is separate from reservations. No refund of unused allowance.
- SEC shared across runs with thread/async serialization, including late sync responses.
- Pinned runtime: FastAPI 0.162.0, Uvicorn 0.54.0, LangGraph 1.2.19,
  langchain-core 1.7.3; complete dependency lock in uv.lock.
- `scripts/run_live_research.py`: explicit `--paid --approve-demo-plan`, checks exact SEC
  ticker set before approval, writes report and compact summary without run tokens.
- A final offline regression fix merges follow-up findings instead of erasing earlier
  grounded fields and prioritizes newly searched follow-up evidence in model context.

## Actual live Phase 3 validation

Two bounded paid runs used FastAPI TestClient → actual LangGraph → SEC/Nebius/Tavily.
The second run after evidence-context trimming returned **partial in 41.2 seconds**:
60/60 available financial metrics and 60/60 matches to reviewed expectations; 17 supported
qualitative findings, 11 explicitly missing fields, 65 sources. No complete live report
is claimed. Reserved: 16 searches, 8 extracted URLs, 24 estimated Tavily credits,
15 model calls, 56,355 input tokens and 11,848 output tokens. Reported model usage:
10,500 prompt tokens, 4,552 completion tokens. Reservations intentionally overestimate.
The first run returned partial in 38.74 sec with 60 metrics and 9 supported/19 missing fields.

Durable compact evidence: `docs/validation/phase3-live-summary.json`. Full second output
is `/tmp/project3a-live-report-v2.json` (temporary, no credentials/tokens). Later follow-up
merge/evidence-priority fixes have offline regression coverage, not another paid run.
Missing fields in the measured second run: HSY products/brands, customers, positioning,
pricing, recent developments; MDLZ geography/recent developments; KHC customers/pricing/
recent developments; GIS recent developments. Partial output is useful but coverage needs
further work. No fixtures were supplied to live research; fixtures only checked its output.

## Checks actually run

- `uv sync --group dev --no-editable`: passed after locked Phase 3 dependencies installed.
- `uv run pytest`: **59 passed in 0.99s**, including the final follow-up regression.
  Tests cover approval/stale/duplicate confirmation, idempotency/auth/capacity, expiration,
  SSE replay/fallback, cancellation/late-result rejection, active timeout, two-branch limit,
  complete mocked report, isolated branch/provider failures, budget reservations/retries,
  bounded schema repeat, citation/quote/news rejection and financial reconciliation.
- `uv run python scripts/export_contracts.py`: passed, three schemas regenerated.
- `python3 -m compileall -q apps/api/src scripts`: passed.
- Four-company live research command passed with a partial report as detailed above.

## Historical Phase 3 limitations (superseded by Phase 4 above)

1. Phase 3 backend is implemented and exercised. Phase 4 is next: implement Next.js/
   TypeScript setup, plan review, progress, five-metric dashboard/charts and evidence views.
   Use the API header token and temporary sessionStorage handle; parse Decimal strings.
2. Exercise actual Uvicorn HTTP streaming and browser disconnect/reconnect/cancel/error
   states in Phase 4. Live runs so far use in-process HTTP transport; no external socket
   or browser streaming validation is claimed. No frontend exists yet.
3. Improve dated-news evidence and qualitative coverage under the same finite budgets.
   No complete live qualitative report yet. Discovery and unsupported-company identity
   behavior have not received a live check. Human review must verify selected websites
   and competitor overlap. Replacement requires cancel/new run.
4. Keep evidence entailment limitations visible. Briefing is deterministic compilation
   of cited positioning/differentiation, not a separately verified comparative synthesis.
   Generic taxonomy mappings for companies outside the reviewed demo remain unverified.
5. Cancellation cannot undo already-dispatched synchronous HTTP costs. Retry/token/credit
   reservations are estimates, not billing guarantees. Extraction redirects/DNS are an
   upstream Tavily boundary. SEC source URLs still identify accession directories.
6. One localhost worker only. Runs/checkpoints/reports vanish on restart; no persistence,
   deployment, authentication or monitoring. Idempotency keys should be unpredictable.
   Do not add paid calls to default tests. Keep requirements separate from observed results.
