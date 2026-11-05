"""Single-worker localhost API. In-memory handles expire and restart loses state."""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import json
import secrets
import time
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from langgraph.types import Command

from .contracts import Contract, ResearchRequest
from .providers import Nebius,Tavily
from .runtime import Budget,Calls,BudgetExceeded
from .research import Research
from .sec import SEC
from .settings import Settings
from .workflow import build_graph,compile_report

TERMINAL={'completed','partial','failed','cancelled','expired'}

class Confirmation(Contract):
    plan_version: int = Field(ge=1)
    approved: bool

@dataclass
class Run:
    id: str
    token: str
    request: ResearchRequest
    status: str='queued'
    plan: object=None
    sources: list=field(default_factory=list)
    results: dict=field(default_factory=dict)
    report: object=None
    error: str | None=None
    budget: Budget=field(default_factory=Budget)
    usage: list=field(default_factory=list)
    events: deque=field(default_factory=lambda:deque(maxlen=256))
    company_progress: dict=field(default_factory=dict)
    activity: deque=field(default_factory=lambda:deque(maxlen=40))
    sequence: int=0
    changed: asyncio.Event=field(default_factory=asyncio.Event)
    task: object=None
    graph: object=None
    touched: float=field(default_factory=time.monotonic)
    expired_at: float | None=None

    def snapshot(self):
        return dict(run_id=self.id,status=self.status,plan=self.plan.model_dump(mode='json') if self.plan else None,
                    error=self.error,budget=dict(reserved=self.budget.used,limits=self.budget.limits),
                    company_progress=self.company_progress.copy(),activity=list(self.activity),
                    model_usage=self.usage,last_event_id=self.sequence,report_available=self.report is not None)

    def emit(self,kind='status'):
        self.sequence+=1
        self.events.append(dict(id=self.sequence,event=kind,data=self.snapshot()))
        self.changed.set()

    def stage(self,status):
        if self.budget.cancelled: return
        self.status=status; self.touched=time.monotonic(); self.emit()

    def progress(self, company_id, stage, **counts):
        # Structured outcomes only: never prompts, query text, upstream bodies or reasoning.
        if self.budget.cancelled or self.status in TERMINAL: return
        allowed={'queued','financials','collecting','analyzing','followup','completed','partial','failed'}
        if stage not in allowed: raise ValueError('Invalid company progress stage')
        record={**self.company_progress.get(company_id,{}),'company_id':company_id,'stage':stage}
        for key in ('sources_collected','search_attempts','supported_fields'):
            if key in counts: record[key]=max(0,int(counts[key]))
        self.company_progress[company_id]=record
        self.activity.append({**record,'at':datetime.now(timezone.utc).isoformat()})
        self.emit('company_progress')

    def retain(self,key,value):
        if self.budget.cancelled: return
        if key in ('plan','sources','report'): setattr(self,key,value)
        else: self.results[key]=value

class Manager:
    def __init__(self,settings,client,research_factory=None):
        self.settings,self.client,self.factory=settings,client,research_factory
        self.runs={}; self.keys={}
        self.sec=SEC(client,settings)
        self.sec_lock=asyncio.Lock()
        self.sweeper=None

    def prune(self):
        now=time.monotonic()
        for rid,r in list(self.runs.items()):
            if r.status=='expired' and now-r.expired_at>=300:
                del self.runs[rid]
                self.keys={k:v for k,v in self.keys.items() if v[1]!=rid}
            elif r.status in TERMINAL|{'awaiting_review'} and r.status!='expired' and now-r.touched>=3600:
                r.budget.cancelled=True
                if r.task and not r.task.done(): r.task.cancel()
                r.status='expired'; r.expired_at=now
                r.plan=None; r.sources=[]; r.results={}; r.report=None; r.graph=None
                r.company_progress.clear(); r.activity.clear()
                r.events.clear(); r.emit()

    async def sweep(self):
        while True:
            await asyncio.sleep(30)
            self.prune()

    def authorized(self,rid,token):
        self.prune()
        r=self.runs.get(rid)
        if not r or not token or not secrets.compare_digest(r.token,token): raise HTTPException(404,'Run not found')
        if r.status=='expired': raise HTTPException(410,'Run expired')
        return r

    def create(self,request,key):
        self.prune()
        fingerprint=hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        if key in self.keys:
            saved,rid=self.keys[key]
            if saved!=fingerprint: raise HTTPException(409,'Idempotency key conflict')
            return self.runs[rid]
        if any(r.status not in TERMINAL for r in self.runs.values()): raise HTTPException(429,'One active run allowed')
        if len(self.runs)>=64: raise HTTPException(429,'Run storage capacity reached')
        r=Run(secrets.token_urlsafe(18),secrets.token_urlsafe(32),request)
        calls=Calls(r.budget,Nebius(self.client,self.settings),Tavily(self.client,self.settings))
        r.usage=calls.usage
        research=self.factory(calls,self.sec) if self.factory else Research(calls,self.sec)
        research.sec_lock=self.sec_lock
        r.graph=build_graph(research,r.stage,r.retain,r.progress)
        self.runs[r.id]=r
        if key: self.keys[key]=(fingerprint,r.id)
        r.emit(); r.task=asyncio.create_task(self.drive(r,dict(request=request.model_dump(mode="json"))))
        return r

    async def drive(self,r,input):
        r.budget.start()
        try:
            # Approval is excluded because each invocation stops at the checkpoint.
            remaining=max(0.001,r.budget.max_seconds-r.budget.active_seconds)
            async with asyncio.timeout(remaining):
                output=await r.graph.ainvoke(input,config={'configurable':{'thread_id':r.id},'recursion_limit':20})
            if r.budget.cancelled: return
            if output.get('__interrupt__'): r.stage('awaiting_review')
            elif r.report: r.stage(r.report.status)
            else: r.error='workflow_incomplete'; r.stage('failed')
        except asyncio.CancelledError:
            if r.status!='expired':
                r.budget.cancelled=True
                if r.plan: r.report=compile_report(r.plan,r.sources,r.results,'Run cancelled; late work discarded.')
                r.status='cancelled'; r.touched=time.monotonic(); r.emit()
        except Exception as error:
            r.error='budget_exhausted' if isinstance(error,(BudgetExceeded,TimeoutError)) else 'research_failed'
            if r.plan:
                r.report=compile_report(r.plan,r.sources,r.results,'Run stopped: '+r.error)
                r.stage('partial')
            else: r.stage('failed')
        finally:
            r.budget.pause()

    async def close(self):
        tasks=[r.task for r in self.runs.values() if r.task and not r.task.done()]
        for r in self.runs.values(): r.budget.cancelled=True
        if self.sweeper: tasks.append(self.sweeper)
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


def create_app(settings=None,research_factory=None):
    settings=settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        with httpx.Client() as client:
            app.state.manager=Manager(settings,client,research_factory)
            app.state.manager.sweeper=asyncio.create_task(app.state.manager.sweep())
            yield
            await app.state.manager.close()
    app=FastAPI(title='Market Research Agent',lifespan=lifespan)
    @app.get('/api/v1/health')
    async def health(): return {'status':'ok'}
    @app.get('/api/v1/ready')
    async def ready():
        configured=bool(settings.nebius_api_key and settings.nebius_model and settings.tavily_api_key and settings.sec_user_agent)
        return {'ready':configured,'live_validation':False}
    @app.post('/api/v1/runs',status_code=202)
    async def create(request:ResearchRequest,idempotency_key:str | None=Header(default=None,max_length=128)):
        r=app.state.manager.create(request,idempotency_key)
        return dict(run_id=r.id,run_token=r.token,status=r.status)
    @app.get('/api/v1/runs/{rid}')
    async def snapshot(rid:str,x_run_token:str | None=Header(default=None)):
        return app.state.manager.authorized(rid,x_run_token).snapshot()
    @app.post('/api/v1/runs/{rid}/confirm',status_code=202)
    async def confirm(rid:str,body:Confirmation,x_run_token:str | None=Header(default=None)):
        r=app.state.manager.authorized(rid,x_run_token)
        if r.status!='awaiting_review' or body.plan_version!=r.plan.plan_version or not body.approved:
            raise HTTPException(409,'Stale or invalid approval')
        # No await between state check and transition: atomic within the one event loop.
        r.stage('researching'); r.task=asyncio.create_task(app.state.manager.drive(r,Command(resume=True)))
        return r.snapshot()
    @app.post('/api/v1/runs/{rid}/cancel')
    async def cancel(rid:str,x_run_token:str | None=Header(default=None)):
        r=app.state.manager.authorized(rid,x_run_token)
        if r.status not in TERMINAL:
            r.budget.cancelled=True
            if r.task and not r.task.done(): r.task.cancel()
            if r.plan: r.report=compile_report(r.plan,r.sources,r.results,'Run cancelled; late work discarded.')
            r.status='cancelled'; r.touched=time.monotonic(); r.emit()
        return r.snapshot()
    @app.get('/api/v1/runs/{rid}/report')
    async def report(rid:str,x_run_token:str | None=Header(default=None)):
        r=app.state.manager.authorized(rid,x_run_token)
        if not r.report: raise HTTPException(409,'Report pending or unavailable')
        return r.report.model_dump(mode='json')
    @app.get('/api/v1/runs/{rid}/events')
    async def events(rid:str,request:Request,x_run_token:str | None=Header(default=None),last_event_id:str | None=Header(default=None)):
        r=app.state.manager.authorized(rid,x_run_token)
        try: cursor=int(last_event_id) if last_event_id is not None else 0
        except ValueError: raise HTTPException(422,'Invalid event cursor')
        if cursor<0: raise HTTPException(422,'Invalid event cursor')
        async def stream():
            nonlocal cursor
            while True:
                if await request.is_disconnected(): return
                r.changed.clear()
                if r.events and (cursor<r.events[0]['id']-1 or cursor>r.sequence):
                    cursor=r.sequence
                    yield f'id: {cursor}\nevent: snapshot\ndata: {json.dumps(r.snapshot())}\n\n'
                else:
                    for event in list(r.events):
                        if event['id']>cursor:
                            cursor=event['id']
                            yield f'id: {cursor}\nevent: {event["event"]}\ndata: {json.dumps(event["data"])}\n\n'
                if r.status in TERMINAL: return
                try: await asyncio.wait_for(r.changed.wait(),timeout=15)
                except TimeoutError: yield ': heartbeat\n\n'
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    return app

app=create_app()
