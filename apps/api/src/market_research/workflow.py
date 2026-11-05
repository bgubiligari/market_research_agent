"""Checkpointed graph; approval node has no pre-interrupt side effects."""
import asyncio
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt
from .contracts import AnalysisReport, Finding, ResearchRequest, ConfirmedPlan, EvidenceSource, FinancialFact, FinancialMetric
from pydantic import BaseModel
from .evidence import REQUIRED_FIELDS
from datetime import datetime, timezone

class State(TypedDict, total=False):
    request: dict
    plan: dict
    sources: list
    results: dict
    report: dict
    approved: bool


def plain(value):
    if isinstance(value, BaseModel): return value.model_dump(mode="json")
    if isinstance(value, dict): return {k:plain(v) for k,v in value.items()}
    if isinstance(value, list): return [plain(v) for v in value]
    return value


def build_graph(research, stage, retain, progress=None):
    research.retain = retain
    research.progress = progress or (lambda *args, **kwargs: None)
    async def resolve(state):
        stage('resolving')
        plan,sources=await research.resolve(ResearchRequest.model_validate(state['request']))
        retain('plan',plan); retain('sources',sources)
        return dict(plan=plain(plan),sources=plain(sources))

    async def approval(state):
        approved=interrupt({'plan':state['plan'],
                            'warnings':['Competitive overlap and company identity require human review.']})
        if approved is not True: raise ValueError('approval_required')
        return dict(approved=True)

    async def branches(state):
        stage('researching')
        plan=ConfirmedPlan.model_validate(state['plan'])
        semaphore=asyncio.Semaphore(2)
        for company in [plan.target,*plan.competitors]:
            research.progress(company.company_id,'queued')
        async def branch(company):
            try:
                async with semaphore:
                    research.calls.budget.check()
                    research.progress(company.company_id,'financials')
                    value=await research.company(company,plan)
                    supported=len({f.field for f in map(Finding.model_validate,value.get('findings',[])) if f.evidence_status in ('supported','not_applicable') and f.field in REQUIRED_FIELDS})
                    complete=supported==len(REQUIRED_FIELDS) and len(value.get('metrics',[]))==15 and all(m.status=='available' for m in map(FinancialMetric.model_validate,value['metrics']))
                    counts=dict(sources_collected=len(value.get('sources',[])),supported_fields=supported)
                    if 'search_attempts' in value: counts['search_attempts']=value['search_attempts']
                    research.progress(company.company_id,'completed' if complete else 'partial',**counts)
            except asyncio.CancelledError: raise
            except Exception:
                research.progress(company.company_id,'failed')
                value=dict(sources=[],findings=[],facts=[],metrics=[],warnings=[f'{company.legal_name}: branch failed safely.'])
            retain(company.company_id,value)
            return company.company_id,value
        values=await asyncio.gather(*(branch(c) for c in [plan.target,*plan.competitors]))
        return dict(results=plain(dict(values)))

    async def validate(state):
        stage('validating')
        compile_report(state['plan'],state['sources'],state['results'])
        return {}

    async def synthesize(state):
        stage('synthesizing')
        report=compile_report(state['plan'],state['sources'],state['results'])
        retain('report',report)
        return dict(report=plain(report))

    graph=StateGraph(State)
    for name,node in [('resolve',resolve),('approval',approval),('research',branches),('validate',validate),('synthesize',synthesize)]: graph.add_node(name,node)
    for a,b in [(START,'resolve'),('resolve','approval'),('approval','research'),('research','validate'),('validate','synthesize'),('synthesize',END)]: graph.add_edge(a,b)
    return graph.compile(checkpointer=InMemorySaver())


def compile_report(plan, resolution_sources, results, extra_warning=None):
    plan=ConfirmedPlan.model_validate(plan)
    resolution_sources=[EvidenceSource.model_validate(s) for s in resolution_sources]
    results={cid:{**value, **{key:[model.model_validate(x) for x in value.get(key,[])] for key,model in [("sources",EvidenceSource),("findings",Finding),("facts",FinancialFact),("metrics",FinancialMetric)]}} for cid,value in results.items()}
    sources=list(resolution_sources); findings=[]; facts=[]; metrics=[]; warnings=[]
    partial=bool(extra_warning)
    for company in [plan.target,*plan.competitors]:
        value=results.get(company.company_id,{})
        sources.extend(value.get('sources',[])); findings.extend(value.get('findings',[]))
        facts.extend(value.get('facts',[])); metrics.extend(value.get('metrics',[])); warnings.extend(value.get('warnings',[]))
        if not value or len(value.get('metrics',[]))!=15 or any(m.status!='available' for m in value.get('metrics',[])) or any(f.evidence_status=='missing' and f.field in REQUIRED_FIELDS for f in value.get('findings',[])) or not set(REQUIRED_FIELDS)<={f.field for f in map(Finding.model_validate,value.get('findings',[])) if f.evidence_status in ('supported','not_applicable')}:
            partial=True
            warnings.append(f'{company.legal_name}: required coverage incomplete.')
    if extra_warning: warnings.append(extra_warning)
    # Briefing uses already-grounded findings, with ownership and references preserved.
    briefing=[f for f in findings if f.field in ('positioning','differentiators')][:8]
    sources=list({s.source_id:s for s in sources}.values())
    return AnalysisReport(as_of=datetime.now(timezone.utc),status='partial' if partial else 'completed',
        plan=plan,briefing=briefing,findings=findings,financial_facts=facts,financial_metrics=metrics,
        sources=sources,warnings=list(dict.fromkeys(warnings)))
