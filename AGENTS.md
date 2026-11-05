# Project context

Build Project 3A Market Research Agent for course submission and later personal use.
Before work, read `docs/HANDOFF.md`, then the relevant sections of
`docs/architecture.md`. The reviewed Word architecture is version 1.1.

## Constraints

- Next.js/TypeScript frontend; FastAPI/Pydantic backend; LangChain/LangGraph agents.
- Nebius inference and Tavily search/extract. Backend-only credentials; never print secrets.
- Configurable target plus three competitors. First demo: HSY vs MDLZ, KHC, GIS.
- Financials: revenue, revenue growth, gross margin, operating margin, operating cash flow growth.
- SEC/official filings for financial evidence; calculate metrics in Python, not the model.
- MVP is local and personal: no accounts, saved report library, scheduled monitoring, or deployment.
- Keep missing evidence explicit. Never invent chart values or represent fixtures as live research.
- No sub-agent delegation unless the user explicitly requests it.

## Continuity

Work toward the current phase in `docs/implementation-plan.md`. At a checkpoint,
update `docs/HANDOFF.md` with actual changes, checks run, limitations, and exact next steps.
Keep requirements and progress separate. Never mark an integration verified without a live check.
Do not copy keys, full logs, or long conversation transcripts into handoffs.

## Checks

Use `uv sync --group dev --no-editable` then `uv run pytest` for the Python foundation.
Generate portable contract schemas with `uv run python scripts/export_contracts.py`.
Future phases must add and document their own meaningful checks. Do not claim UI or agent execution
works until those components exist and have been exercised.
