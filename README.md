# Market Research Agent

Project 3A competitor analysis: target company plus three competitors, with cited research
and five annual financial metrics. Demo: HSY vs MDLZ, KHC, and GIS.

Phase 2 provider checks and four-company filing reconciliation are complete. Phase 3
includes FastAPI lifecycle/SSE, a checkpointed LangGraph workflow, human approval,
budgets, cancellation and partial reports. See the handoff for exact live-run evidence.
Phase 4 adds the local Next.js/TypeScript app, plan approval, replayable progress, and cited financial/research views.

## Start here

- [Current handoff](docs/HANDOFF.md)
- [Architecture and decisions](docs/architecture.md)
- [Implementation phases](docs/implementation-plan.md)
- [Dashboard wireframe](docs/wireframe.md)
- [Reviewed architecture document](docs/market_research_agent_architecture_v1_1.docx)

## Run foundation checks

Requires Python 3.11 or later and uv.

```sh
uv sync --group dev --no-editable
uv run pytest
uv run python scripts/export_contracts.py
```

JSON schemas in `docs/contracts/` are generated from the Python models. Cross-field rules
are enforced by Pydantic validators; generated JSON Schema alone does not encode all of them.
No API keys are needed for these checks. See `.env.example` for backend environment variables. Settings deliberately do not auto-load
`.env`; export values into the process environment or use an explicit environment loader.
Never paste credentials into chat or commit them.

## Phase 2 live validation

Copy `.env.example` to `.env` in the repository root (ignored by Git), then fill in
your private values locally. The commands below explicitly load that file. Set `NEBIUS_API_KEY`, `NEBIUS_MODEL`, `TAVILY_API_KEY`, and `SEC_USER_AGENT` in the backend
process environment. Use an actual contact email in the SEC identifying User-Agent.
No model ID is assumed: the selected model must pass the capability probe.

```sh
# Public SEC requests only; saves evidence for review, not a verified reconciliation.
uv run --env-file .env python scripts/check_integrations.py --sec --cutoff 2026-10-31 --output /tmp/demo-financials.json
# Explicit paid opt-in: two small Nebius calls, one Tavily search and one extraction.
uv run --env-file .env python scripts/check_integrations.py --paid
```

Clients use finite timeouts, no redirects, and no automatic retries. Retryable errors expose
a safe code and Retry-After metadata so the run manager can reserve budget before retrying.
SEC requests are spaced at least 250ms apart within each adapter instance; the API shares
one instance and a lock across runs. Provider bodies/prompts are not logged.
The extraction URL validator rejects nonpublic DNS results, credentials, and nonstandard ports;
Tavily owns fetching and redirect behavior, which still needs an upstream security review.
Do not add a local arbitrary-URL fetcher without DNS pinning and per-redirect validation.

For each HSY, MDLZ, KHC, and GIS result, verify four annual periods of revenue, reported gross
profit (or matching cost of sales), reported operating income and operating cash flow against
the official annual filings. Record filing URLs/accessions, exact units and fiscal dates,
restatements, scope/accounting changes, and independently computed expected metrics for three
periods. Compare those expected values with the saved calculation output. A successful HTTP
response or synthetic test is not this reconciliation. Facts retain base currency amounts
(scale 1), never chart-scaled millions; fiscal years are labeled by period-end year.

Provider references: [Nebius API](https://docs.tokenfactory.nebius.com/api-reference/introduction),
[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search),
[Tavily Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract), and
[SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
HTTP adapters avoid coupling Phase 2 to an agent framework; LangChain/LangGraph integration
is implemented in Phase 3. Exact dependency versions are pinned in `uv.lock`.

## Phase 3 local API

```sh
PYTHONPATH=apps/api/src uv run --env-file .env uvicorn market_research.api:app --host 127.0.0.1 --port 8000 --workers 1
# Explicit paid run through FastAPI TestClient and the real graph/providers:
uv run --env-file .env python scripts/run_live_research.py --paid --approve-demo-plan --output /tmp/project3a-live-report.json
```

Use `/api/v1/runs` to create a configurable target/three-peer request. Save the returned
`run_id` and secret `run_token` temporarily; send `X-Run-Token` on all run routes. An
`Idempotency-Key` retries creation; use a fresh unpredictable key per request. Poll the
snapshot until `awaiting_review`, inspect the plan, then POST `/confirm` with
`{"plan_version":1,"approved":true}`. To replace companies, cancel and create a new run.
The live demo script approves only the exact SEC-resolved HSY/MDLZ/KHC/GIS plan.

`GET /events` is fetch-based SSE with `Last-Event-ID` replay, snapshot fallback and
heartbeats. Disconnecting does not cancel research. `POST /cancel` is repeatable.
`GET /report` returns 409 until a report is available, including a useful partial
report after an approved run fails or is cancelled. Unknown/wrong-token handles return
404; an authorized expired handle returns 410 for five minutes. Terminal/paused runs
expire after an hour. Restarting loses everything. One active run and at most 64 stored
handles keep this local MVP bounded. The local web app below consumes these routes.

Research uses LangGraph checkpoints/approval and LangChain message primitives with
Nebius structured analysis. At most two companies research concurrently; each receives an equal share of the remaining
budget. Three field-specific searches and relevant page extractions precede one focused
follow-up per company. Financial arithmetic remains Python-only. Quotations must match stored
excerpts; source ownership is checked. This does not prove model entailment. Findings
are explicitly marked inferred and retain the supporting quote; missing fields remain
visible. Undated evidence cannot establish recent developments. The briefing compiles
cited positioning/differentiation findings deterministically.

Reservations include retries: 24 searches, 20 extracted URLs, estimated 60 Tavily credits,
28 model calls, 60,000 input tokens and 12,000 output tokens; ten active minutes exclude
approval time. Input reservations use conservative UTF-8 byte counts including schema;
unused reservations are not refunded. These estimates are not a provider billing cap.
Calls have finite timeouts; retryable errors get one retry, invalid structured output
gets one repeat attempt, authentication failures are not retried. Retry-After longer
than 30 seconds ends the attempt rather than retrying early. Cancellation discards
late responses; already-dispatched synchronous HTTP calls can finish and incur cost.

Official four-company statement expectations and comparability notes live in
`tests/fixtures/reconciled_financials.json`; these are reviewed regression evidence,
not research fixtures returned by the live API. The UI should label revenue as reported
net sales/revenue and reserve XBRL concept names for evidence details.


Retrieval selects representative excerpts for each field instead of source prefixes.
Publication metadata survives extraction; ISO, date-only and RFC publication dates are
supported. News searches request explicit publication-date windows and local validation
rejects old/future evidence. Pricing is outside default research and does not count toward missing coverage, per the
user’s scope change: these companies do not sell directly comparable products.
See `docs/validation/` and HANDOFF.md for measured coverage and remaining missing fields.


## Phase 4 local web app

Requires Node.js 20.9+ (validated with 24.21.0), npm, and the Python setup above.
Run the real API and frontend in separate terminals from the repository root:

```sh
PYTHONPATH=apps/api/src uv run --env-file .env uvicorn market_research.api:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
npm ci --prefix apps/web
npm --prefix apps/web run dev -- --port 3002
```

Open http://127.0.0.1:3002. Only the backend loads root `.env`. The Next.js route handler
uses server-only `API_ORIGIN` (default `http://127.0.0.1:8000`). No provider keys belong in
Next.js or `NEXT_PUBLIC_*`. Both servers bind localhost. Production-local alternative:
`npm --prefix apps/web run build`, then `npm --prefix apps/web run start -- --port 3002`.
The build uses webpack because Turbopack worker port binding failed in this validation environment.

The workspace separates Setup, Run and Briefing. During research, the pipeline and
company activity feed show real backend stages and collected-source counts. Results
expand into Overview, Companies, Comparison, Financials, Recent developments and Sources.
Citations and financial values open an evidence drawer; detailed annual values and
comparability notes expand on demand. Mobile uses bottom navigation.

Review identities/websites and overlap before approving. Cancel and start a new comparison
to replace companies. The browser stores only `{run_id, run_token}` in sessionStorage,
never report data. Replay cursors stay in memory; reload replays from zero. Reports vanish
when the backend restarts. Charts parse Decimal strings explicitly, retain negative values,
leave missing values empty, and separate currencies. Tables preserve fiscal dates and link
to exact filing inputs. Source excerpts are rendered as text, never HTML.

### Frontend checks (no paid calls)

```sh
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
# In a separate terminal: offline graph/API with clearly labeled test evidence.
PYTHONPATH=apps/api/src uv run uvicorn scripts.serve_ui_validation:app --host 127.0.0.1 --port 8001 --no-access-log
# Restart the frontend against that server (do not load .env):
API_ORIGIN=http://127.0.0.1:8001 npm --prefix apps/web run start -- --port 3002
npm --prefix apps/web run test:browser
```

Browser checks use installed Google Chrome (`channel: chrome`) and require the offline
marker before creating any run. Set `WEB_URL` for another frontend port. Test-only controls
exist only in `scripts/serve_ui_validation.py`, never in the real app. The harness uses
reviewed financial regression fixtures and synthetic qualitative statements, explicitly
labeled OFFLINE TEST. Default checks never invoke paid providers.

One optional real browser validation (bounded paid run) is separate:

```sh
# Real API + frontend pointing to :8000 must already be running.
node scripts/check_browser_live.mjs --paid
```

It checks exact demo tickers before approval, reload/reconnect, all 60 financial rows,
report rendering and terminal reload. It writes a compact credential-free summary to
`docs/validation/phase4-browser-live-summary.json`, and a temporary screenshot in `/tmp`.
It does not independently re-reconcile the new run's financial values; Phase 2/3 hold
that evidence. Latest browser run was partial; see the handoff for exact coverage.
