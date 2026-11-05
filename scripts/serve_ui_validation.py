"""Offline-only browser harness. Never use as the production API or live evidence.
Run: PYTHONPATH=apps/api/src uv run uvicorn scripts.serve_ui_validation:app --port 8001
"""
import asyncio
import json
from pathlib import Path
from market_research.api import create_app
from market_research.settings import Settings
from market_research.contracts import CompanyIdentity, ConfirmedPlan, FinancialFact, Finding
from market_research.research import source
from market_research.financials import calculate_metrics
from market_research.evidence import REQUIRED_FIELDS

FIXTURE = json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/reconciled_financials.json').read_text())

class OfflineResearch:
    def __init__(self,calls,sec): self.calls=calls
    async def resolve(self,request):
        await asyncio.sleep(.3)
        if request.target=='FAIL': raise ValueError('offline failure')
        names=['HSY','MDLZ','KHC','GIS']
        sources=[source(n,'https://example.com/'+n,'OFFLINE TEST identity','Synthetic identity for browser validation; not live research.') for n in names]
        companies=[CompanyIdentity(company_id=n,legal_name='OFFLINE TEST '+n,website='https://example.com/'+n,ticker=n,resolution_source_ids=[s.source_id]) for n,s in zip(names,sources)]
        return ConfirmedPlan(plan_version=1,target=companies[0],competitors=companies[1:],focus=request.target,news_lookback_days=request.news_lookback_days),sources
    async def company(self,company,plan):
        await asyncio.sleep(1)
        n=company.company_id
        facts={role:[FinancialFact.model_validate(f) for f in rows] for role,rows in FIXTURE[n]['facts'].items()}
        metrics=[m for r in facts['revenue'][:3] for m in calculate_metrics(n,r.period,facts)]
        s=source(n,'https://example.com/evidence/'+n,'OFFLINE TEST evidence','Synthetic qualitative statement. Not live evidence.')
        findings=[Finding(company_id=n,field=f,statement='Synthetic qualitative statement. Not live evidence.',basis='inferred',evidence_status='supported',source_ids=[s.source_id]) for f in REQUIRED_FIELDS]
        if plan.focus!='COMPLETE' and n=='KHC':
            findings=[f for f in findings if f.field!='recent_developments']+[Finding(company_id=n,field='recent_developments',statement='No accepted recent developments.',basis='observed',evidence_status='missing',limitations=['OFFLINE TEST missing dated evidence'])]
        return dict(sources=[s],findings=findings,facts=list({f.fact_id:f for rows in facts.values() for f in rows}.values()),metrics=metrics,warnings=['OFFLINE TEST fixture report. Not live research.'])

app=create_app(Settings(nebius_api_key='offline',nebius_model='offline',tavily_api_key='offline',sec_user_agent='offline-test'),OfflineResearch)

# Test-only controls, absent from the real API. No network provider is invoked.
@app.post('/__test/expire/{rid}')
async def expire(rid:str):
    app.state.manager.runs[rid].touched-=3601
    app.state.manager.prune()
    return {'ok':True}

from fastapi.responses import JSONResponse
@app.middleware('http')
async def offline_marker(request, call_next):
    if request.url.path == '/api/v1/ready':
        return JSONResponse({'ready':True,'offline_validation':True})
    return await call_next(request)
