"""SEC identity and consolidated annual facts. Concept mappings require filing review."""
from datetime import date
from decimal import Decimal
import hashlib
import re
import time
import threading

from .contracts import FinancialFact, FiscalPeriod
from .providers import HTTPProvider, ProviderError

DEMO_TICKERS = ("HSY", "MDLZ", "KHC", "GIS")
CONCEPTS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"),
    "gross_profit": ("GrossProfit",),
    "cost_of_sales": ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"),
    "operating_income": ("OperatingIncomeLoss",),
    "ocf": ("NetCashProvidedByUsedInOperatingActivities",),
}

# KHC consolidated net sales: 2025 10-K, statements of income p.51.
# Do not generalize tax-inclusive revenue to companies without filing review.
COMPANY_CONCEPTS = {
    "0001637459": {"revenue": ("RevenueFromContractWithCustomerIncludingAssessedTax",)},
}


class SEC(HTTPProvider):
    def __init__(self, client, settings):
        super().__init__(client, settings, "sec")
        self._last_request = 0.0
        self._request_lock = threading.Lock()

    def get(self, url: str) -> dict:
        # Survives async cancellation while a synchronous request finishes.
        with self._request_lock:
            return self._get(url)

    def _get(self, url: str) -> dict:
        agent = self.settings.sec_user_agent
        if not agent or "@" not in agent:
            raise ProviderError("sec", "identifying_user_agent_required")
        time.sleep(max(0, 0.25 - (time.monotonic() - self._last_request)))
        try:
            return self.request("GET", url, headers={"User-Agent": agent, "Accept-Encoding": "gzip, deflate"})
        finally:
            self._last_request = time.monotonic()

    def resolve(self, ticker: str) -> dict:
        ticker = ticker.strip().upper()
        rows = self.get("https://www.sec.gov/files/company_tickers.json")
        matches = [r for r in rows.values() if isinstance(r, dict) and r.get("ticker", "").upper() == ticker]
        if len(matches) != 1:
            raise ProviderError("sec", "identity_not_found_or_ambiguous")
        row = matches[0]
        return {"ticker": row["ticker"], "legal_name": row["title"], "cik": str(row["cik_str"]).zfill(10),
                "source_url": "https://www.sec.gov/files/company_tickers.json"}

    def companyfacts(self, cik: str) -> dict:
        if not re.fullmatch(r"\d{10}", cik):
            raise ValueError("CIK requires ten digits")
        data = self.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        if str(data.get("cik", "")).zfill(10) != cik:
            raise ProviderError("sec", "identity_mismatch")
        return data


def select_annual_facts(payload: dict, company_id: str, cutoff: date, currency: str = "USD") -> dict[str, list[FinancialFact]]:
    """Prefer latest filing at cutoff per exact period, then configured concept priority.

    FY labels describe the filing, not necessarily the comparative fact year. Period-end
    year labels are used instead. No frames or quarterly/YTD values enter arithmetic.
    """
    cik = str(payload["cik"]).zfill(10)
    gaap = payload.get("facts", {}).get("us-gaap", {})
    selected = {}
    for role, defaults in CONCEPTS.items():
        concepts = COMPANY_CONCEPTS.get(cik, {}).get(role, defaults)
        periods = {}
        for priority, concept in enumerate(concepts):
            for row in gaap.get(concept, {}).get("units", {}).get(currency, []):
                try:
                    start, end, filed = (date.fromisoformat(row[k]) for k in ("start", "end", "filed"))
                    value = Decimal(str(row["val"]))
                    accession = row["accn"]
                    if (row["form"] not in ("10-K", "10-K/A") or not 350 <= (end-start).days <= 380
                            or filed > cutoff or end > filed or not value.is_finite()
                            or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)):
                        continue
                except (KeyError, ValueError, TypeError, ArithmeticError):
                    continue
                key = (start, end)
                rank = (filed, -priority, accession)
                if key in periods and rank <= periods[key][0]:
                    continue
                identity = f"{company_id}:{concept}:{currency}:{start}:{end}:{accession}"
                fact = FinancialFact(fact_id=hashlib.sha256(identity.encode()).hexdigest()[:32],
                    company_id=company_id, concept=f"us-gaap:{concept}", value=value, unit=currency,
                    period=FiscalPeriod(start=start, end=end, fiscal_year=end.year), form=row["form"],
                    filing_date=filed, accession=accession,
                    source_url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/")
                periods[key] = (rank, fact)
        selected[role] = sorted((v[1] for v in periods.values()), key=lambda f: f.period.end, reverse=True)[:4]
    return selected
