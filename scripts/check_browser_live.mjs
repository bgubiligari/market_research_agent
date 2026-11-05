// Explicit paid browser validation; not included in npm test or test:browser.
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const require=createRequire(new URL('../apps/web/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
if(!process.argv.includes('--paid'))throw new Error('Explicit --paid required');
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];const eventHeaders=[];page.on('pageerror',e=>errors.push(e.message));
page.on('request',request=>{if(request.url().endsWith('/events'))eventHeaders.push({cursor:request.headers()['last-event-id'],token_header_present:!!request.headers()['x-run-token']});});
const started=Date.now();
try {
 await page.goto(process.env.WEB_URL||'http://127.0.0.1:3002');
 await page.getByRole('button',{name:'Load HSY demo'}).click();
 await page.getByRole('button',{name:'Review research plan'}).click();
 await page.getByRole('heading',{name:'awaiting review'}).waitFor({timeout:120000});
 const identities=await page.locator('.identity').allTextContents();
 if(!['HSY','MDLZ','KHC','GIS'].every((ticker,i)=>identities[i]?.includes(ticker)))throw new Error('Unexpected resolved plan; approval withheld');
 await page.reload();await page.getByRole('heading',{name:'awaiting review'}).waitFor();
 const approved=Date.now();await page.getByRole('button',{name:'Approve companies'}).click();
 await page.getByRole('button',{name:'Refresh status / reconnect'}).click();
 await page.getByLabel('Research report').waitFor({timeout:180000});
 const status=await page.locator('.report-meta .badge').innerText();
 await page.getByRole('button',{name:'Financials',exact:true}).click();
 await page.getByText('Detailed annual values & filing evidence',{exact:true}).click();
 const rows=await page.locator('.financial-details tbody tr').count();if(rows!==60)throw new Error(`Expected 60 financial rows, received ${rows}`);
 const report=await page.evaluate(async()=>{const h=JSON.parse(sessionStorage.getItem('project3a.run'));return (await fetch(`/api/v1/runs/${h.run_id}/report`,{headers:{'X-Run-Token':h.run_token}})).json();});
 await page.screenshot({path:'/tmp/project3a-phase4-live-financials.png',fullPage:false});
 await page.reload();await page.getByLabel('Research report').waitFor();
 const summary={checked_at:new Date().toISOString(),transport:'Chrome → Next.js route handler → external Uvicorn → real LangGraph/SEC/Nebius/Tavily',status,elapsed_seconds:(Date.now()-started)/1000,post_approval_seconds:(Date.now()-approved)/1000,financial_values:report.financial_metrics.length,available_values:report.financial_metrics.filter(m=>m.status==='available').length,missing:report.findings.filter(f=>f.evidence_status==='missing').map(f=>({company_id:f.company_id,ticker:[report.plan.target,...report.plan.competitors].find(c=>c.company_id===f.company_id)?.ticker,field:f.field})),source_count:report.sources.length,browser_errors:errors,event_connections:eventHeaders,terminal_reload:true,fixtures_supplied:false};
 await writeFile('docs/validation/phase4-browser-live-summary.json',JSON.stringify(summary,null,2)+'\n');
 console.log(JSON.stringify(summary,null,2));
 if(errors.length)throw new Error('Browser errors recorded');
} finally {await browser.close();}
