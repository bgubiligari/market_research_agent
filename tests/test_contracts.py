from datetime import date

import pytest
from pydantic import ValidationError

from market_research.contracts import (
    AnalysisReport, CompanyIdentity, ConfirmedPlan, FinancialMetric,
    Finding, FiscalPeriod, MetricName, ResearchRequest,
)


def company(symbol: str) -> CompanyIdentity:
    return CompanyIdentity(company_id=symbol, legal_name=symbol,
                           website=f"https://{symbol.lower()}.example.com",
                           resolution_source_ids=[f"source-{symbol}"])


def plan() -> ConfirmedPlan:
    return ConfirmedPlan(plan_version=1, target=company("HSY"),
                         competitors=[company(x) for x in ("MDLZ", "KHC", "GIS")],
                         news_lookback_days=90)


def metric(**overrides) -> FinancialMetric:
    values = dict(company_id="HSY", metric="gross_margin", value="40.5", unit="percent",
                  period=FiscalPeriod(start=date(2025, 1, 1), end=date(2025, 12, 31),
                                      fiscal_year=2025),
                  input_fact_ids=["gross-profit", "revenue"], status="available")
    return FinancialMetric(**(values | overrides))


def test_supplied_and_discovered_request_paths():
    assert ResearchRequest(target=" HSY ", competitors=["MDLZ", "KHC", "GIS"]).target == "HSY"
    assert ResearchRequest(target="HSY", discovery_mode=True).competitors == []


@pytest.mark.parametrize("values", [
    dict(target="HSY"),
    dict(target="HSY", competitors=["MDLZ", "KHC"]),
    dict(target="HSY", competitors=["MDLZ", "KHC", "GIS"], discovery_mode=True),
    dict(target="HSY", competitors=["MDLZ", " hsy ", "GIS"]),
    dict(target="HSY", competitors=["MDLZ", "MDLZ", "GIS"]),
    dict(target=" ", discovery_mode=True),
])
def test_invalid_research_scope_is_rejected(values):
    with pytest.raises(ValidationError):
        ResearchRequest(**values)


def test_confirmed_plan_rejects_different_aliases_for_same_sec_entity():
    data = plan().model_dump()
    data["target"]["cik"] = "0000000001"
    data["competitors"][0]["cik"] = "0000000001"
    with pytest.raises(ValidationError, match="distinct cik"):
        ConfirmedPlan(**data)


def test_supported_findings_require_evidence():
    with pytest.raises(ValidationError, match="require evidence"):
        Finding(company_id="HSY", field="positioning", statement="A factual claim",
                basis="observed", evidence_status="supported")


def test_negative_margins_are_values_but_missing_is_not_zero():
    assert metric(value="-5").value == -5
    result = metric(metric="operating_cash_flow_growth", value=None,
                    status="not_meaningful", reason="Prior OCF is nonpositive")
    assert result.value is None
    with pytest.raises(ValidationError):
        metric(status="unavailable", value="0", reason="Missing evidence")


@pytest.mark.parametrize("overrides", [
    dict(value="NaN"), dict(value="Infinity"), dict(unit="USD"),
    dict(metric="revenue", unit="percent"), dict(input_fact_ids=[]),
])
def test_chart_values_require_finite_values_units_and_provenance(overrides):
    with pytest.raises(ValidationError):
        metric(**overrides)


def test_report_rejects_unresolved_source_references():
    with pytest.raises(ValidationError, match="unknown source"):
        AnalysisReport(as_of="2026-10-31T16:00:00Z", status="completed", plan=plan(),
                       briefing=[], findings=[], financial_facts=[], financial_metrics=[], sources=[])


def test_contract_contains_all_five_financial_metrics():
    assert set(MetricName) == {"revenue", "revenue_growth", "gross_margin", "operating_margin",
                               "operating_cash_flow_growth"}
