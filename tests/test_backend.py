import asyncio
import json
import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from market_research.api import create_app
from market_research.contracts import CompanyIdentity,ConfirmedPlan,Finding
from market_research.research import source, Research, Claims, Claim
from market_research.runtime import Budget,Calls,BudgetExceeded,retry_delay
from market_research.settings import Settings
from market_research.providers import ProviderError

REQUEST=dict(target='HSY',competitors=['MDLZ','KHC','GIS'])

class FakeResearch:
    calls_before_approval=0
    def __init__(self,calls,sec): self.calls=calls
    async def resolve(self,request):
        sources=[source(str(i),'https://example.com/'+str(i),'identity','Official company identity') for i in range(4)]
        companies=[CompanyIdentity(company_id=str(i),legal_name=name,website='https://example.com',resolution_source_ids=[sources[i].source_id]) for i,name in enumerate([request.target,*request.competitors])]
        return ConfirmedPlan(plan_version=1,target=companies[0],competitors=companies[1:],news_lookback_days=90),sources
    async def company(self,company,plan):
        type(self).calls_before_approval+=1
        if company.company_id=='2': raise ProviderError('test','failed')
        return dict(sources=[],findings=[Finding(company_id=company.company_id,field='pricing',statement='No pricing evidence',basis='observed',evidence_status='missing',limitations=['Missing'])],facts=[],metrics=[],warnings=[])


def wait(client,handle,statuses):
    headers={'X-Run-Token':handle['run_token']}
    for _ in range(200):
        value=client.get('/api/v1/runs/'+handle['run_id'],headers=headers).json()
        if value['status'] in statuses: return value
        time.sleep(.01)
    raise AssertionError(value)

@pytest.fixture
def client():
    with TestClient(create_app(Settings(),FakeResearch)) as client: yield client


def test_lifecycle_approval_partial_report_and_sse(client):
    FakeResearch.calls_before_approval=0
    handle=client.post('/api/v1/runs',json=REQUEST).json(); rid=handle['run_id']; h={'X-Run-Token':handle['run_token']}
    paused=wait(client,handle,{'awaiting_review'})
    assert paused['plan']['target']['legal_name']=='HSY'
    assert FakeResearch.calls_before_approval==0
    assert client.get(f'/api/v1/runs/{rid}/report',headers=h).status_code==409
    assert client.post(f'/api/v1/runs/{rid}/confirm',headers=h,json=dict(plan_version=2,approved=True)).status_code==409
    assert client.post(f'/api/v1/runs/{rid}/confirm',headers=h,json=dict(plan_version=1,approved=True)).status_code==202
    assert client.post(f'/api/v1/runs/{rid}/confirm',headers=h,json=dict(plan_version=1,approved=True)).status_code==409
    wait(client,handle,{'partial'})
    report=client.get(f'/api/v1/runs/{rid}/report',headers=h).json()
    assert report['status']=='partial' and len(report['findings'])==3
    assert any('branch failed' in w for w in report['warnings'])
    events=client.get(f'/api/v1/runs/{rid}/events',headers=h).text
    ids=[int(line[4:]) for line in events.splitlines() if line.startswith('id: ')]
    assert ids==sorted(set(ids)) and 'awaiting_review' in events and 'synthesizing' in events
    replay=client.get(f'/api/v1/runs/{rid}/events',headers={**h,'Last-Event-ID':str(ids[-2])}).text
    assert f'id: {ids[-1]}\n' in replay and f'id: {ids[-2]}\n' not in replay
    assert client.get(f'/api/v1/runs/{rid}/events',headers={**h,'Last-Event-ID':'-1'}).status_code==422


def test_idempotency_capacity_auth_and_validation(client):
    h=client.post('/api/v1/runs',headers={'Idempotency-Key':'a'},json=REQUEST).json()
    assert client.post('/api/v1/runs',headers={'Idempotency-Key':'a'},json=REQUEST).json()['run_id']==h['run_id']
    assert client.post('/api/v1/runs',headers={'Idempotency-Key':'a'},json={**REQUEST,'target':'OTHER'}).status_code==409
    assert client.post('/api/v1/runs',json=REQUEST).status_code==429
    assert client.get('/api/v1/runs/'+h['run_id']).status_code==404
    assert client.get('/api/v1/runs/unknown',headers={'X-Run-Token':h['run_token']}).status_code==404
    assert client.post('/api/v1/runs',json={'target':'x'}).status_code==422
    assert client.get('/api/v1/health').json()=={'status':'ok'}
    assert client.get('/api/v1/ready').json()['ready'] is False


def test_cancel_paused_repeatable_and_expiry(client):
    handle=client.post('/api/v1/runs',json=REQUEST).json(); rid=handle['run_id']; h={'X-Run-Token':handle['run_token']}
    wait(client,handle,{'awaiting_review'})
    for _ in range(2): assert client.post(f'/api/v1/runs/{rid}/cancel',headers=h).json()['status']=='cancelled'
    assert client.get(f'/api/v1/runs/{rid}/report',headers=h).json()['status']=='partial'
    assert client.post(f'/api/v1/runs/{rid}/confirm',headers=h,json=dict(plan_version=1,approved=True)).status_code==409
    run=client.app.state.manager.runs[rid]
    run.touched-=3601
    assert client.get(f'/api/v1/runs/{rid}',headers=h).status_code==410
    assert client.get(f'/api/v1/runs/{rid}').status_code==404
    run.expired_at-=301
    assert client.get(f'/api/v1/runs/{rid}',headers=h).status_code==404


def test_sse_snapshot_fallback(client):
    handle=client.post('/api/v1/runs',json=REQUEST).json(); rid=handle['run_id']; h={'X-Run-Token':handle['run_token']}
    wait(client,handle,{'awaiting_review'})
    client.post(f'/api/v1/runs/{rid}/cancel',headers=h)
    run=client.app.state.manager.runs[rid]
    for _ in range(300): run.emit()
    data=client.get(f'/api/v1/runs/{rid}/events',headers=h).text
    assert 'event: snapshot' in data


def test_resolution_failure_safe():
    class Broken(FakeResearch):
        async def resolve(self,request): raise RuntimeError('SECRET raw upstream body')
    with TestClient(create_app(Settings(),Broken)) as client:
        h=client.post('/api/v1/runs',json=REQUEST).json()
        state=wait(client,h,{'failed'})
        assert state['error']=='research_failed' and 'SECRET' not in json.dumps(state)


def test_active_cancel_discards_late_result():
    class Slow(FakeResearch):
        async def company(self,company,plan):
            await asyncio.sleep(.3)
            return await super().company(company,plan)
    with TestClient(create_app(Settings(),Slow)) as client:
        handle=client.post('/api/v1/runs',json=REQUEST).json(); rid=handle['run_id']; h={'X-Run-Token':handle['run_token']}
        wait(client,handle,{'awaiting_review'})
        client.post(f'/api/v1/runs/{rid}/confirm',headers=h,json=dict(plan_version=1,approved=True))
        client.post(f'/api/v1/runs/{rid}/cancel',headers=h)
        time.sleep(.4)
        assert client.get(f'/api/v1/runs/{rid}',headers=h).json()['status']=='cancelled'
        assert client.app.state.manager.runs[rid].results=={}


def test_budget_reservation_atomic_and_pause():
    b=Budget(limits=dict(model_calls=1,input_tokens=10),max_seconds=1)
    b.reserve(model_calls=1,input_tokens=5)
    with pytest.raises(BudgetExceeded): b.reserve(model_calls=1,input_tokens=5)
    assert b.used==dict(model_calls=1,input_tokens=5)
    b.active_seconds=2
    with pytest.raises(BudgetExceeded): b.check()
    b.active_seconds=0; b.start(); b.pause()
    assert b.active_start is None


def test_retry_counts_and_auth_not_retried():
    async def run():
        b=Budget(); calls=Calls(b,None,None); attempts=[]
        def flaky():
            attempts.append(1)
            if len(attempts)==1: raise ProviderError('test','temporarily_unavailable','0')
            return 'ok'
        assert await calls.invoke(flaky,dict(searches=1))=='ok'
        assert b.used['searches']==2
        def auth(): raise ProviderError('test','authentication_failed')
        with pytest.raises(ProviderError): await calls.invoke(auth,dict(searches=1))
        assert b.used['searches']==3
        def long_wait(): raise ProviderError('test','temporarily_unavailable','120')
        with pytest.raises(ProviderError): await calls.invoke(long_wait,dict(searches=1))
        assert b.used['searches']==4
    asyncio.run(run())
    assert retry_delay('0')==0


def test_schema_repair_bounded():
    async def run():
        b=Budget(); calls=Calls(b,None,None); attempts=[]
        def invalid():
            attempts.append(1); raise ProviderError('test','invalid_structured_output','0')
        with pytest.raises(ProviderError): await calls.invoke(invalid,dict(model_calls=1),repair=True)
        assert len(attempts)==2 and b.used['model_calls']==2
    asyncio.run(run())


def test_analysis_rejects_unknown_sources_nonliteral_quotes_and_undated_news():
    async def run():
        s=source('0','https://example.com','test','The company sells chocolate bars and other snacks.')
        class Stub:
            async def structured(self,*args):
                return Claims(claims=[Claim(field='products_brands',statement='Chocolate bars',source_id=s.source_id,quote='sells chocolate bars'),Claim(field='pricing',statement='Cheap',source_id=s.source_id,quote='Invented quotation'),Claim(field='geography',statement='Worldwide',source_id='unknown',quote='The company sells'),Claim(field='recent_developments',statement='Recent launch',source_id=s.source_id,quote='sells chocolate bars')])
        r=Research(Stub(),None)
        company=CompanyIdentity(company_id='0',legal_name='Example',website='https://example.com',resolution_source_ids=[s.source_id])
        findings=await r.analyze(company,[s],90)
        assert len(findings)==1 and findings[0].field=='products_brands'
    asyncio.run(run())


def test_graph_enforces_two_branches_and_completed_coverage():
    from pathlib import Path
    from market_research.contracts import FinancialFact,FinancialMetric
    from market_research.financials import calculate_metrics
    from market_research.research import FIELDS
    reviewed=json.loads((Path(__file__).parent/'fixtures/reconciled_financials.json').read_text())
    class Complete(FakeResearch):
        active=0; peak=0
        async def company(self,company,plan):
            type(self).active+=1; type(self).peak=max(type(self).peak,type(self).active)
            await asyncio.sleep(.03)
            rows=reviewed[company.legal_name]['facts']
            facts={role:[FinancialFact.model_validate({**f,'company_id':company.company_id}) for f in values] for role,values in rows.items()}
            metrics=[m for r in facts['revenue'][:3] for m in calculate_metrics(company.company_id,r.period,facts)]
            evidence=source(company.company_id,'https://example.com/'+company.company_id,'statement','Company sells food brands to consumers.')
            findings=[Finding(company_id=company.company_id,field=f,statement='Supported fixture claim',source_ids=[evidence.source_id],basis='observed',evidence_status='supported') for f in FIELDS]
            type(self).active-=1
            return dict(sources=[evidence],findings=findings,facts=[f for values in facts.values() for f in values],metrics=metrics,warnings=[])
    with TestClient(create_app(Settings(),Complete)) as client:
        handle=client.post('/api/v1/runs',json=REQUEST).json(); base='/api/v1/runs/'+handle['run_id']; h={'X-Run-Token':handle['run_token']}
        wait(client,handle,{'awaiting_review'})
        client.post(base+'/confirm',headers=h,json=dict(plan_version=1,approved=True))
        assert wait(client,handle,{'completed'})['status']=='completed'
        report=client.get(base+'/report',headers=h).json()
        assert len(report['financial_metrics'])==60 and len(report['findings'])==24
        assert Complete.peak==2


def test_budget_exhaustion_after_approval_returns_partial():
    class Exhausted(FakeResearch):
        async def company(self,company,plan):
            self.calls.budget.reserve(searches=100)
    with TestClient(create_app(Settings(),Exhausted)) as client:
        handle=client.post('/api/v1/runs',json=REQUEST).json(); base='/api/v1/runs/'+handle['run_id']; h={'X-Run-Token':handle['run_token']}
        wait(client,handle,{'awaiting_review'})
        client.post(base+'/confirm',headers=h,json=dict(plan_version=1,approved=True))
        assert wait(client,handle,{'partial'})['report_available']
        assert client.get(base+'/report',headers=h).json()['warnings']


def test_active_timeout_retains_plan():
    class Timeout(FakeResearch):
        async def company(self,company,plan): await asyncio.sleep(1)
    with TestClient(create_app(Settings(),Timeout)) as client:
        handle=client.post('/api/v1/runs',json=REQUEST).json(); base='/api/v1/runs/'+handle['run_id']; h={'X-Run-Token':handle['run_token']}
        wait(client,handle,{'awaiting_review'})
        client.app.state.manager.runs[handle['run_id']].budget.max_seconds=.03
        client.post(base+'/confirm',headers=h,json=dict(plan_version=1,approved=True))
        result=wait(client,handle,{'partial'})
        assert result['error']=='budget_exhausted'
        assert client.get(base+'/report',headers=h).json()['plan']['target']['legal_name']=='HSY'


def test_real_research_preserves_financials_when_qualitative_provider_fails():
    from pathlib import Path
    from market_research.research import Queries
    reviewed=json.loads((Path(__file__).parent/'fixtures/reconciled_financials.json').read_text())['KHC']
    payload={'cik':1637459,'facts':{'us-gaap':{}}}
    for rows in reviewed['facts'].values():
        for f in rows:
            rows=payload['facts']['us-gaap'].setdefault(f['concept'].split(':')[1],{'units':{'USD':[]}})['units']['USD']
            rows.append(dict(start=f['period']['start'],end=f['period']['end'],filed=f['filing_date'],form=f['form'],accn=f['accession'],val=f['value']))
    class SECStub:
        def companyfacts(self,cik): return payload
    class CallsStub:
        budget=Budget()
        async def structured(self,*args): return Queries(query='KHC official products')
        async def search(self,*args): raise ProviderError('tavily','authentication_failed')
    async def run():
        research=Research(CallsStub(),SECStub())
        s=source('khc','https://example.com','KHC identity','KHC identity evidence')
        company=CompanyIdentity(company_id='khc',legal_name='Kraft Heinz',website='https://example.com',cik='0001637459',resolution_source_ids=[s.source_id])
        # Only company and lookback are used in this direct branch check.
        class Plan: focus=None; geography=None; news_lookback_days=90
        retained={}; research.retain=lambda k,v:retained.update({k:v})
        value=await research.company(company,Plan())
        assert len(value['metrics'])==15 and all(m.status=='available' for m in value['metrics'])
        assert len(value['findings'])==6 and all(f.evidence_status=='missing' for f in value['findings'])
        assert len(retained['khc']['metrics'])==15
    asyncio.run(run())


def test_followup_uses_new_evidence_without_erasing_grounded_fields(monkeypatch):
    from market_research.research import Queries
    monkeypatch.setattr('market_research.research.public_url',lambda url:None)
    class Stub:
        budget=Budget()
        searches=0
        async def structured(self,*args): return Queries(query='official products')
        async def search(self,*args):
            self.searches+=1
            return {'results':[dict(url=f'https://example.com/{self.searches}',title='Evidence',content='Verified supporting company evidence.') ]}
        async def extract(self,urls): return dict(results=[],failed_results=[])
    class FollowupResearch(Research):
        passes=0
        async def analyze(self,company,sources,lookback):
            self.passes+=1
            if self.passes==2: assert str(sources[0].url)=='https://example.com/4'
            return [Finding(company_id=company.company_id,field='products_brands' if self.passes==1 else 'geography',statement='Grounded claim',source_ids=[sources[0].source_id],basis='inferred',evidence_status='supported')]
    async def run():
        research=FollowupResearch(Stub(),None)
        company=CompanyIdentity(company_id='0',legal_name='Example',website='https://example.com',resolution_source_ids=['identity'])
        class Plan: focus=None; geography=None; news_lookback_days=90
        value=await research.company(company,Plan())
        assert {f.field for f in value['findings'] if f.evidence_status=='supported'}=={'products_brands','geography'}
        assert research.calls.searches==4 and research.passes==2
    asyncio.run(run())


def test_company_progress_is_replayed_and_retained_in_snapshots(client):
    handle=client.post('/api/v1/runs',json=REQUEST).json()
    headers={'X-Run-Token':handle['run_token']}; rid=handle['run_id']
    wait(client,handle,{'awaiting_review'})
    assert client.get(f'/api/v1/runs/{rid}',headers=headers).json()['company_progress']=={}
    client.post(f'/api/v1/runs/{rid}/confirm',headers=headers,json={'plan_version':1,'approved':True})
    final=wait(client,handle,{'partial'})
    assert len(final['company_progress'])==4
    assert final['company_progress']['2']['stage']=='failed'
    assert final['company_progress']['0']['stage']=='partial'
    assert final['company_progress']['0']['supported_fields']==0
    assert all('at' in event for event in final['activity'])
    events=client.get(f'/api/v1/runs/{rid}/events',headers=headers).text
    assert 'event: company_progress' in events
    run=client.app.state.manager.runs[rid]
    before=run.sequence
    run.progress('0','collecting',sources_collected=999)
    assert run.sequence==before  # terminal/late events are discarded
    assert 'run_token' not in events


def test_progress_counts_are_allowlisted_and_cancellation_discards_late_events():
    from market_research.api import Run
    from market_research.contracts import ResearchRequest
    r=Run('id','secret',ResearchRequest(**REQUEST))
    r.progress('0','collecting',sources_collected=3,search_attempts=2,prompt='must not leak')
    assert r.snapshot()['company_progress']['0']['sources_collected']==3
    assert 'prompt' not in json.dumps(r.snapshot())
    r.budget.cancelled=True
    r.progress('0','completed',sources_collected=4)
    assert r.snapshot()['company_progress']['0']['stage']=='collecting'
