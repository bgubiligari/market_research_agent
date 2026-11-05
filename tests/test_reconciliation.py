"""Official statement expectations; no network or paid calls in this suite."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from market_research.contracts import FinancialFact
from market_research.financials import calculate_metrics
from market_research.sec import select_annual_facts

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/reconciled_financials.json').read_text())

@pytest.mark.parametrize('ticker', FIXTURE)
def test_official_statement_reconciliation(ticker):
    reviewed = FIXTURE[ticker]
    payload = {'cik': {'HSY':47111,'MDLZ':1103982,'KHC':1637459,'GIS':40704}[ticker], 'facts': {'us-gaap': {}}}
    for rows in reviewed['facts'].values():
        for f in rows:
            units = payload['facts']['us-gaap'].setdefault(f['concept'].split(':')[1], {'units': {'USD': []}})['units']['USD']
            units.append(dict(start=f['period']['start'],end=f['period']['end'],filed=f['filing_date'],form=f['form'],accn=f['accession'],val=f['value']))
    facts = select_annual_facts(payload,ticker,date(2026,10,31))
    for role, expected in reviewed['expected_inputs'].items():
        assert [f.value for f in facts[role]] == list(map(Decimal,expected))
    for i, revenue in enumerate(facts['revenue'][:3]):
        metrics = calculate_metrics(ticker,revenue.period,facts)
        assert len(metrics)==5 and all(m.status=='available' for m in metrics)
        for m, expected in zip(metrics,reviewed['expected_metrics'][i]):
            assert abs(m.value-Decimal(expected)) <= Decimal(reviewed['tolerance'])
    if ticker=='KHC':
        assert 'IncludingAssessedTax' in facts['revenue'][0].concept
        assert calculate_metrics(ticker,facts['revenue'][0].period,facts)[3].value < 0
