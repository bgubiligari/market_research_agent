"""Explicit bounded paid API demo. Saves report/summary, never the run token."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api/src'))
from fastapi.testclient import TestClient
from market_research.api import create_app


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paid',action='store_true')
    p.add_argument('--approve-demo-plan',action='store_true',help='Approve only the exact SEC-resolved HSY/MDLZ/KHC/GIS plan')
    p.add_argument('--output',type=Path,default=Path('/tmp/project3a-live-report.json'))
    args=p.parse_args()
    if not args.paid or not args.approve_demo_plan: p.error('Both explicit paid and demo-plan approval flags are required')
    started=time.monotonic()
    with TestClient(create_app()) as client:
        response=client.post('/api/v1/runs',json=dict(target='HSY',competitors=['MDLZ','KHC','GIS']))
        response.raise_for_status(); handle=response.json(); headers={'X-Run-Token':handle['run_token']}
        base='/api/v1/runs/'+handle['run_id']; approved=False
        while time.monotonic()-started<660:
            snapshot=client.get(base,headers=headers).json()
            if snapshot['status']=='awaiting_review' and not approved:
                plan=snapshot['plan']
                tickers=[c['ticker'] for c in [plan['target'],*plan['competitors']]]
                if tickers!=['HSY','MDLZ','KHC','GIS']:
                    client.post(base+'/cancel',headers=headers)
                    raise SystemExit('Demo identity mismatch; cancelled without approval')
                client.post(base+'/confirm',headers=headers,json=dict(plan_version=plan['plan_version'],approved=True)).raise_for_status()
                approved=True
            if snapshot['status'] in ('completed','partial','failed','cancelled'): break
            time.sleep(.5)
        else:
            client.post(base+'/cancel',headers=headers)
            snapshot=client.get(base,headers=headers).json()
        report=client.get(base+'/report',headers=headers)
        output=dict(status=snapshot['status'],elapsed_seconds=round(time.monotonic()-started,2),budget=snapshot['budget'],model_usage=snapshot.get('model_usage',[]),error=snapshot['error'])
        if report.status_code==200:
            output['report']=report.json()
            from decimal import Decimal
            expected=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/reconciled_financials.json').read_text())
            checks=[]
            for company in [output['report']['plan']['target'],*output['report']['plan']['competitors']]:
                rows=[m for m in output['report']['financial_metrics'] if m['company_id']==company['company_id']]
                for i in range(3):
                    for m,value in zip(rows[i*5:i*5+5],expected[company['ticker']]['expected_metrics'][i]):
                        checks.append(m['value'] is not None and abs(Decimal(m['value'])-Decimal(value))<=Decimal('0.000001'))
            output['reconciled_metric_checks']=dict(checked=len(checks),passed=sum(checks))
            output['summary']=dict(companies=4,financial_metrics=len(output['report']['financial_metrics']),available_metrics=sum(m['status']=='available' for m in output['report']['financial_metrics']),supported_findings=sum(f['evidence_status']=='supported' for f in output['report']['findings']),missing_findings=sum(f['evidence_status']=='missing' for f in output['report']['findings']),sources=len(output['report']['sources']))
        args.output.write_text(json.dumps(output,indent=2)+'\n')
        print(json.dumps({k:v for k,v in output.items() if k!='report'},indent=2),flush=True)
        return 0 if snapshot['status'] in ('completed','partial') and output.get('summary',{}).get('financial_metrics')==60 and output.get('reconciled_metric_checks')==dict(checked=60,passed=60) else 1

if __name__=='__main__': raise SystemExit(main())
