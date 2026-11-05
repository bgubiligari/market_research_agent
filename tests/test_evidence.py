import asyncio
from datetime import datetime, timedelta, timezone
import json

import pytest
from market_research.evidence import publication_date,page_publication,window,queries
from market_research.research import Research,source,Claims,Claim
from market_research.contracts import CompanyIdentity
from market_research.runtime import Budget,ScopedBudget,BudgetExceeded

@pytest.mark.parametrize('value', ['2026-10-30','2026-10-30T12:00:00Z','Fri, 30 Oct 2026 12:00:00 GMT'])
def test_supported_publication_dates(value):
    assert publication_date(value).date().isoformat()=='2026-10-30'
    assert publication_date(value).tzinfo is not None

@pytest.mark.parametrize('value', [None,'yesterday','2026-10-30T12:00:00','not-a-date'])
def test_ambiguous_dates_remain_missing(value): assert publication_date(value) is None


def test_page_date_does_not_confuse_event_with_publication():
    assert page_publication('Acquisition expected 2026-10-01. Retrieved 2026-10-30') is None
    assert page_publication('Published on: 2026-10-30').date().isoformat()=='2026-10-30'
    assert page_publication('{"datePublished": "2026-10-30T12:00:00Z"}').hour==12


def test_relevant_window_survives_long_navigation():
    text='Navigation menu '*1000+'\nOur principal customers are retailers and foodservice distributors.\nFooter'
    value=window(text,['customer','retailer'],200)
    assert 'principal customers' in value and len(value)<=200
    assert 'Our principal customers are retailers and foodservice distributors.' in text


def test_context_includes_news_and_each_field_despite_source_order():
    sources=[source('c',f'https://example.com/{i}','Brands','Our brands and product portfolio include snacks.') for i in range(8)]
    dated=source('c','https://example.com/news','News','Announced a new acquisition.',published=datetime.now(timezone.utc))
    sources.append(dated)
    context=Research.analysis_context(sources)
    assert next(c for c in context if c['field']=='recent_developments')['source_id']==dated.source_id


def test_extraction_retains_publication_and_source_provenance():
    class Calls:
        async def extract(self,urls):
            return dict(results=[dict(url=urls[0],raw_content='Navigation '*1000+'\nOur customers include retailers and distributors.')])
    async def run():
        old=source('c','https://example.com/news','Original title','Original news summary',kind='news',published=publication_date('2026-10-30'))
        values=await Research(Calls(),None).extract_sources([old],('customers',))
        merged=Research.merge_sources([old],values)[0]
        assert merged.published_at==old.published_at and merged.title==old.title and merged.source_type=='news'
        assert 'Original news summary' in merged.excerpt and 'Our customers' in merged.excerpt
    asyncio.run(run())


def test_company_budget_cannot_consume_another_share_and_failed_global_is_atomic():
    global_budget=Budget(limits=dict(searches=4))
    first=ScopedBudget(global_budget,dict(searches=2)); second=ScopedBudget(global_budget,dict(searches=2))
    first.reserve(searches=2)
    with pytest.raises(BudgetExceeded): first.reserve(searches=1)
    assert global_budget.used['searches']==2
    second.reserve(searches=2)
    third=ScopedBudget(global_budget,dict(searches=2))
    with pytest.raises(BudgetExceeded): third.reserve(searches=1)
    assert third.used=={} and global_budget.used['searches']==4


def test_pricing_requires_literal_currency_and_package_and_news_within_lookback():
    async def run():
        now=datetime.now(timezone.utc)
        price=source('c','https://example.com/item','Retail listing','Chocolate bar 1.55 oz $1.48 each')
        news=source('c','https://example.com/news','News','Announced a new product launch.',published=now-timedelta(days=91))
        class Stub:
            async def structured(self,*args):
                return Claims(claims=[Claim(field='pricing',statement='Retail listing: 1.55 oz at $1.48',source_id=price.source_id,quote=price.excerpt),Claim(field='recent_developments',statement='Launch',source_id=news.source_id,quote=news.excerpt)])
        company=CompanyIdentity(company_id='c',legal_name='Example',website='https://example.com',resolution_source_ids=['identity'])
        research=Research(Stub(),None)
        research.analysis_fields=('pricing','recent_developments')
        findings=await research.analyze(company,[price,news],90)
        assert [f.field for f in findings]==['pricing']
        assert 'No comparable-product' in findings[0].limitations[1]
        price.excerpt='The company uses premium pricing.'
        assert await research.analyze(company,[price,news],90)==[]
    asyncio.run(run())


def test_targeted_search_groups_use_configured_identity_and_scope():
    company=CompanyIdentity(company_id='c',legal_name='Example Foods',website='https://example.org',resolution_source_ids=['id'])
    class Plan: geography='Canada'; focus='snacks'
    steps=queries(company,Plan())
    assert len(steps)==3 and all('Example Foods' in query for query,_,_ in steps)
    assert 'site:example.org' in steps[0][0] and 'Canada' in steps[0][0]
    assert set(f for _,fields,_ in steps for f in fields)==set(__import__('market_research.research',fromlist=['FIELDS']).FIELDS)
    assert steps[-1][2] is True


def test_context_excludes_old_future_news_and_limits_followup_fields():
    now=datetime.now(timezone.utc)
    sources=[source('c','https://example.com/old','Old','Announced launch acquisition press release.',published=now-timedelta(days=91)),source('c','https://example.com/future','Future','Announced launch acquisition.',published=now+timedelta(days=1)),source('c','https://example.com/current','Current','New business update.',published=now-timedelta(days=2))]
    context=Research.analysis_context(sources,('recent_developments',),90)
    assert len(context)==1 and context[0]['source_id']==sources[2].source_id


def test_provider_requests_explicit_news_publication_window():
    import httpx
    from market_research.providers import Tavily
    from market_research.settings import Settings
    captured=[]
    def handler(request):
        captured.append(json.loads(request.content)); return httpx.Response(200,json={'results':[]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        Tavily(client,Settings(tavily_api_key='test')).search('Example news',news_days=90)
    body=captured[0]
    assert body['include_published_date'] and body['filter_by_published_date']
    assert 'days' not in body  # API rejects days combined with start_date/end_date
    assert (datetime.fromisoformat(body['end_date'])-datetime.fromisoformat(body['start_date'])).days==90


def test_pricing_not_required_or_searched_by_default():
    from market_research.evidence import REQUIRED_FIELDS
    from market_research.research import FIELDS
    assert len(REQUIRED_FIELDS)==6 and 'pricing' not in REQUIRED_FIELDS
    assert FIELDS==REQUIRED_FIELDS
    company=CompanyIdentity(company_id='c',legal_name='Example',website='https://example.org',resolution_source_ids=['id'])
    class Plan: geography=None; focus=None
    steps=queries(company,Plan())
    assert all('pricing' not in fields for _,fields,_ in steps)
    assert all('price' not in query.lower() for query,_,_ in steps)
