# Implementation phases

Use one fresh chat per phase if helpful. Repository files carry the durable context; do not
assume a new chat remembers its predecessor. Keep a phase in the same chat through its checks,
then update HANDOFF.md. The user has authorized implementation; this is a coordination plan,
not a requirement to seek permission for every routine engineering step.

| Phase | Scope | Exit evidence |
| --- | --- | --- |
| 1 Contracts and design | Repository context, Pydantic models, JSON schemas, low fidelity wireframe | Contract invariant tests and schema export pass; UI design is identified as a draft |
| 2 Integrations | Nebius capability spike, Tavily search/extract, SEC identity/fact adapter, deterministic financial calculations | Pinned dependencies; mock tests; explicit live checks; four demo-company reconciliations |
| 3 Research backend | FastAPI lifecycle/SSE, LangGraph agents, approval, budgets, cancellation, partial reports | API and graph tests including failure paths; four-company research API run |
| 4 Web app | Next.js setup/review/progress/dashboard, five metrics, charts and evidence | Type/build checks and browser verification of complete, partial, reconnect and error states |
| 5 Validation and submission | Measured live HSY demo, docs, sample output, recording script | Reproducible setup, cited reconciled figures, bounded usage, final test evidence |

Do not run live paid integrations silently as part of the default test suite. Never paste keys
into handoff prompts. If credentials are not configured, continue mocks and report live checks
as pending rather than declaring success. Model selection is an integration outcome.

## Current status

Phases 1 and 2 complete. Phase 2 has live Nebius/Tavily checks, a verified KHC net-sales
mapping, and official filing-linked expectations for 60 demo metric values. Phase 3
backend is implemented with lifecycle/SSE, approval, bounded graph research, budgets,
cancellation and partial reports. Offline API/graph/financial checks pass. The latest live
four-company run returned all 60 reconciled financial values and 23/24 required qualitative
fields after pricing was removed from scope; KHC recent developments remains missing. See
`docs/validation/phase3-retrieval-summary.json` and HANDOFF.md. This is not a
verified complete research report. Phase 4 Next.js UI is implemented and verified with type/build checks, four frontend unit tests,
six browser tests against external offline Uvicorn, and one bounded real browser/provider run.
The new run was partial with 60/60 financial values available and 23/24 required fields
(KHC customers missing). See `docs/validation/phase4-browser-live-summary.json`. Phase 5
validation/submission is next; no complete live qualitative report is claimed.


The user subsequently approved a Phase 4 layout revision: compact workspace/sidebar,
review pipeline, structured company activity, expanded briefing/matrix, financial summary
and contextual evidence drawer. This revision uses offline production-browser validation;
no new provider run or complete live report is claimed. See
`docs/validation/phase4-redesign-summary.json` and the latest HANDOFF checkpoint.
