"""Synthetic payloads test behavior; these are not reconciled company financials."""
from datetime import date
from decimal import Decimal
import json

import httpx
import pytest
from pydantic import BaseModel

from market_research.settings import Settings
from market_research.providers import Nebius, Tavily, ProviderError, public_url
from market_research.sec import SEC, select_annual_facts, CONCEPTS, DEMO_TICKERS
from market_research.financials import calculate_metrics


def payload(ticker="HSY"):
    facts = {}
    for role, amount in (("revenue", 200), ("cost_of_sales", 80), ("operating_income", -20), ("ocf", 50)):
        rows = []
        for year, val in ((2023, amount/2), (2024, amount)):
            rows.append(dict(start=f"{year}-01-01", end=f"{year}-12-31", filed="2025-02-01",
                             form="10-K", accn="0000000001-25-000001", val=val, fy=2024))
        facts[CONCEPTS[role][0]] = {"units": {"USD": rows}}
    return dict(cik=1, facts={"us-gaap": facts})


@pytest.mark.parametrize("ticker", DEMO_TICKERS)
def test_all_five_metrics_synthetic(ticker):
    facts = select_annual_facts(payload(), ticker, date(2025, 3, 1))
    metrics = calculate_metrics(ticker, facts["revenue"][0].period, facts)
    assert [m.value for m in metrics] == [Decimal(200), Decimal(100), Decimal(60), Decimal(-10), Decimal(100)]
    assert all(m.status == "available" for m in metrics)


def test_annual_cutoff_restatements_and_interim_exclusion():
    data = payload()
    rows = data["facts"]["us-gaap"][CONCEPTS["revenue"][0]]["units"]["USD"]
    original = rows[-1]
    rows.extend([dict(original, val=300, filed="2025-04-01", accn="0000000001-25-000002"),
                 dict(original, val=999, start="2024-10-01"),
                 dict(original, val=888, form="10-Q")])
    before = select_annual_facts(data, "HSY", date(2025, 3, 1))["revenue"]
    after = select_annual_facts(data, "HSY", date(2025, 5, 1))["revenue"]
    assert len(before) == 2 and before[0].value == 200
    assert after[0].value == 300
    assert after[1].period.fiscal_year == 2023  # comparative FY is not the filing FY


@pytest.mark.parametrize("prior", [0, -25])
def test_ocf_not_meaningful_retains_amounts(prior):
    data = payload()
    data["facts"]["us-gaap"][CONCEPTS["ocf"][0]]["units"]["USD"][0]["val"] = prior
    facts = select_annual_facts(data, "HSY", date(2025, 3, 1))
    metric = calculate_metrics("HSY", facts["revenue"][0].period, facts)[-1]
    assert metric.value is None and metric.status == "not_meaningful"
    assert metric.breakdown.prior_amount == prior
    assert metric.breakdown.absolute_change == 50-prior


def test_missing_and_currency_mismatch():
    facts = select_annual_facts(payload(), "HSY", date(2025, 3, 1))
    facts["cost_of_sales"][0].unit = "EUR"
    facts["ocf"] = []
    metrics = calculate_metrics("HSY", facts["revenue"][0].period, facts)
    assert metrics[2].status == metrics[-1].status == "unavailable"


def test_nebius_capability_payloads():
    requests = []
    def handler(req):
        body = json.loads(req.content)
        requests.append(body)
        message = {"content": '{"ok":true}'} if "response_format" in body else {
            "tool_calls": [{"function": {"name": "probe", "arguments": '{"ok":true}'}}]}
        return httpx.Response(200, json={"choices": [{"message": message}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Nebius(client, Settings(nebius_api_key="test-secret", nebius_model="test-model")).capability_check()
    assert result["tool_calls"] and requests[0]["max_tokens"] == 512
    assert "test-secret" not in repr(Settings(nebius_api_key="test-secret"))


@pytest.mark.parametrize("status,code", [(401,"authentication_failed"),(429,"temporarily_unavailable"),
                                         (503,"temporarily_unavailable"),(302,"request_failed")])
def test_safe_provider_failures(status, code):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text="SECRET", headers={"Retry-After":"2"}))) as client:
        with pytest.raises(ProviderError) as error:
            Tavily(client, Settings(tavily_api_key="secret")).search("Hershey")
    assert error.value.code == code and "SECRET" not in str(error.value)


def test_tavily_search_and_extract(monkeypatch):
    monkeypatch.setattr("market_research.providers.socket.getaddrinfo", lambda *a, **k: [(2,1,6,"",("8.8.8.8",443))])
    bodies = []
    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json={"results": [], "failed_results": [{"url":"https://example.com", "error":"unavailable"}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = Tavily(client, Settings(tavily_api_key="test"))
        provider.search("HSY", news_days=90)
        assert provider.extract(["https://example.com"])["failed_results"]
    assert "days" not in bodies[0] and bodies[0]["topic"] == "news"
    assert bodies[0]["start_date"] < bodies[0]["end_date"]


@pytest.mark.parametrize("url", ["http://example.com", "https://u:p@example.com", "https://example.com:8080"])
def test_unsafe_url(url):
    with pytest.raises(ValueError): public_url(url)


def test_private_dns_rejected(monkeypatch):
    monkeypatch.setattr("market_research.providers.socket.getaddrinfo", lambda *a, **k: [(2,1,6,"",("127.0.0.1",443))])
    with pytest.raises(ValueError): public_url("https://example.com")


def test_sec_identity_and_configuration():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"0":{
        "ticker":"HSY", "title":"Hershey", "cik_str":47111}}))) as client:
        with pytest.raises(ProviderError): SEC(client, Settings()).resolve("HSY")
        assert SEC(client, Settings(sec_user_agent="Research contact@example.com")).resolve("HSY")["cik"] == "0000047111"


def test_negative_current_ocf_and_zero_revenue():
    facts = select_annual_facts(payload(), "HSY", date(2025, 3, 1))
    facts["ocf"][0].value = Decimal(-50)
    facts["revenue"][0].value = Decimal(0)
    metrics = calculate_metrics("HSY", facts["revenue"][0].period, facts)
    assert metrics[-1].value == -300
    assert metrics[2].status == metrics[3].status == "unavailable"


def test_53_week_year_and_missing_prior():
    data = payload()
    for concept in data["facts"]["us-gaap"].values():
        concept["units"]["USD"][-1].update(start="2023-12-25", end="2024-12-29")
    facts = select_annual_facts(data, "GIS", date(2025, 3, 1))
    metrics = calculate_metrics("GIS", facts["revenue"][0].period, facts)
    assert metrics[0].value == 200
    assert metrics[1].status == "unavailable"  # no contiguous prior annual period


def test_malformed_json_and_structured_output():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="not json"))) as client:
        with pytest.raises(ProviderError): Tavily(client, Settings(tavily_api_key="test")).search("HSY")
    class Schema(BaseModel):
        ok: bool
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"choices":[]}))) as client:
        with pytest.raises(ProviderError): Nebius(client, Settings(nebius_api_key="test",nebius_model="test")).structured([],Schema)


def test_fiscal_week_disclosure():
    from market_research.contracts import FiscalPeriod
    from market_research.financials import fiscal_warnings
    period = FiscalPeriod(start=date(2023,12,25), end=date(2024,12,29), fiscal_year=2024)
    assert "53 weeks" in fiscal_warnings([period])[0]
