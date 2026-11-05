"""Deterministic field queries, publication dates and representative evidence windows."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlsplit

FIELD_TERMS = {
    'products_brands': ('brand', 'product', 'portfolio'),
    'differentiators': ('innovation', 'different', 'advantage', 'quality'),
    'customers': ('customer', 'retailer', 'distributor', 'walmart', 'foodservice'),
    'positioning': ('strategy', 'leading', 'consumer', 'position'),
    'geography': ('geograph', 'countries', 'international', 'north america', 'markets'),
    'pricing': ('price', '$', 'ounce', ' oz', 'per unit', 'pack'),
    'recent_developments': ('announced', 'launch', 'acquisition', 'press release'),
}


REQUIRED_FIELDS=tuple(field for field in FIELD_TERMS if field != "pricing")


def publication_date(value):
    """Only explicit provider/page publication metadata; never retrieval/event dates."""
    if not isinstance(value,str) or not value.strip(): return None
    try:
        parsed=datetime.fromisoformat(value.strip().replace('Z','+00:00'))
    except ValueError:
        try: parsed=parsedate_to_datetime(value.strip())
        except (ValueError,TypeError,OverflowError): return None
    # A date-only publication is day precision, normalized to UTC midnight.
    if parsed.tzinfo is None:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value.strip()): return None
        parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def page_publication(text):
    # Accept explicitly labeled metadata only. A date elsewhere on a page may be an event.
    pattern=r'(?:datePublished|article:published_time|Published(?:\s+(?:on|date))?)\s*[\"\s:=|]+(\d{4}-\d{2}-\d{2}(?:T[\d:.]+(?:Z|[+-]\d{2}:\d{2}))?)'
    match=re.search(pattern,text,re.I)
    return publication_date(match.group(1)) if match else None


def window(text, terms, limit=650):
    """Choose literal windows from the full page, skipping long navigation prefixes."""
    text=''.join(c for c in str(text) if c in '\n\t' or ord(c)>=32)
    if len(text)<=limit: return text
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    ranked=sorted(enumerate(lines),key=lambda pair:(-sum(t in pair[1].lower() for t in terms),pair[0]))
    if len(lines)>1 and ranked and any(t in ranked[0][1].lower() for t in terms):
        chosen=[]; remaining=limit
        for _,line in ranked[:4]:
            if not any(t in line.lower() for t in terms): continue
            chosen.append(line[:remaining]); remaining-=len(chosen[-1])+1
            if remaining<=0: break
        return '\n'.join(chosen)[:limit]
    lower=text.lower()
    indices=[lower.find(t) for t in terms if t in lower]
    start=max(0,min(indices)-100) if indices else 0
    return text[start:start+limit]


def queries(company,plan):
    name=company.legal_name
    host=urlsplit(str(company.website)).hostname or ''
    official=f'site:{host} ' if host else ''
    focus=' '.join(x for x in (plan.geography,plan.focus) if x)
    return [
        (f'{official}{name} brands products portfolio strategy differentiation {focus}',('products_brands','differentiators','positioning'),False),
        (f'{name} annual report 10-K principal customers retailers distributors geographic markets net sales',('customers','geography'),False),
        (f'{name} company newsroom press release announces business developments',('recent_developments',),True),
    ]


def followup_query(company,missing):
    # One pass with a focused query for the most consequential missing evidence group.
    groups=[('recent_developments',),('products_brands','customers','geography'),('positioning','differentiators'),('pricing',)]
    group=next((g for g in groups if set(g)&missing),tuple(sorted(missing)))
    terms=' '.join(t for f in group if f in missing for t in FIELD_TERMS[f][:2])
    return f'{company.legal_name} official {terms}',tuple(f for f in group if f in missing)
