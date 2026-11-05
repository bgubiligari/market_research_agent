"""Explicit live checks; paid endpoints require --paid. Never prints upstream bodies."""
import argparse
from datetime import date
from pathlib import Path
import sys
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))
import httpx
from market_research.settings import Settings
from market_research.providers import Nebius, Tavily, ProviderError
from market_research.sec import SEC, DEMO_TICKERS, select_annual_facts
from market_research.financials import calculate_metrics, fiscal_warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paid", action="store_true", help="Opt in to Nebius and Tavily calls")
    parser.add_argument("--sec", action="store_true", help="Fetch demo SEC company facts")
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, help="Save SEC inputs/metrics for manual filing reconciliation")
    args = parser.parse_args()
    if not args.paid and not args.sec:
        parser.error("Select --sec and/or --paid explicitly")
    results, failed = {}, False
    with httpx.Client() as client:
        settings = Settings()
        if args.paid:
            for name, check in (("nebius", lambda: Nebius(client, settings).capability_check()),
                                ("tavily", lambda: tavily_check(client, settings))):
                try: results[name] = check()
                except ProviderError as error:
                    results[name] = {"error": error.code}
                    failed = True
        if args.sec:
            sec = SEC(client, settings)
            for ticker in DEMO_TICKERS:
                try:
                    identity = sec.resolve(ticker)
                    facts = select_annual_facts(sec.companyfacts(identity["cik"]), ticker, args.cutoff)
                    periods = [f.period for f in facts["revenue"]][:3]
                    results[ticker] = {"identity": identity, "cutoff": str(args.cutoff),
                        "verification": "SEC retrieval only; manual annual-report reconciliation pending",
                        "warnings": fiscal_warnings(periods),
                        "facts": [f.model_dump(mode="json") for rows in facts.values() for f in rows],
                        "metrics": [m.model_dump(mode="json") for p in periods for m in calculate_metrics(ticker,p,facts)]}
                    if not periods:
                        results[ticker]["error"] = "annual_revenue_missing"
                        failed = True
                except ProviderError as error:
                    results[ticker] = {"error": error.code}
                    failed = True
    if args.output:
        args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: {"status": "failed" if "error" in v else "retrieved", **({"error":v["error"]} if "error" in v else {})}
                      for k,v in results.items()}, indent=2))
    return 1 if failed else 0


def tavily_check(client, settings):
    provider = Tavily(client, settings)
    search = provider.search("Hershey official company brands")
    extracted = provider.extract(["https://www.thehersheycompany.com/"])
    if not search["results"] or not extracted["results"]:
        raise ProviderError("tavily", "empty_live_results")
    return {"search": True, "extract": True}


if __name__ == "__main__":
    raise SystemExit(main())
