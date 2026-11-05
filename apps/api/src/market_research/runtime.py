"""Run-local reservations. Every retry reserves again; no billing guarantee."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import time

from pydantic import ValidationError
from .providers import ProviderError


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    limits: dict = field(default_factory=lambda: dict(searches=24, extracted_urls=20, tavily_credits=60,
                                                     model_calls=28, input_tokens=60000, output_tokens=12000))
    used: dict = field(default_factory=dict)
    active_seconds: float = 0
    active_start: float | None = None
    max_seconds: float = 600
    cancelled: bool = False

    def check(self):
        if self.cancelled:
            raise asyncio.CancelledError()
        elapsed = self.active_seconds + (time.monotonic()-self.active_start if self.active_start is not None else 0)
        if elapsed >= self.max_seconds:
            raise BudgetExceeded('active_time_exhausted')

    def reserve(self, **amounts):
        self.check()
        if any(self.used.get(k, 0)+v > self.limits[k] for k,v in amounts.items()):
            raise BudgetExceeded('call_budget_exhausted')
        for k,v in amounts.items():
            self.used[k] = self.used.get(k,0)+v

    def start(self):
        self.active_start = time.monotonic()

    def pause(self):
        if self.active_start is not None:
            self.active_seconds += time.monotonic()-self.active_start
            self.active_start = None


def retry_delay(value):
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = (parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            seconds = 1
    return max(0, seconds)


class Calls:
    def __init__(self, budget, nebius, tavily):
        self.budget, self.nebius, self.tavily = budget, nebius, tavily
        self.usage = []

    def scoped(self, limits):
        child=Calls(ScopedBudget(self.budget,limits),self.nebius,self.tavily)
        child.usage=self.usage
        return child

    async def invoke(self, fn, reservation, *, repair=False):
        for attempt in range(2):
            self.budget.reserve(**reservation)
            try:
                value = await asyncio.to_thread(fn)
                self.budget.check()  # discard late results after cancel/deadline
                return value
            except ProviderError as error:
                retryable = error.code in ('temporarily_unavailable','invalid_response_or_transport') or (repair and error.code=='invalid_structured_output')
                if attempt or not retryable:
                    raise
                delay = retry_delay(error.retry_after)
                # Do not retry earlier than Retry-After; refuse waits exceeding the run.
                if delay > 30:
                    raise
                await asyncio.sleep(delay)

    async def search(self, query, news_days=None):
        return await self.invoke(lambda: self.tavily.search(query,news_days=news_days),dict(searches=1,tavily_credits=1))

    async def extract(self, urls):
        return await self.invoke(lambda: self.tavily.extract(urls),dict(extracted_urls=len(urls),tavily_credits=len(urls)))

    async def structured(self, messages, schema):
        # UTF-8 bytes conservatively reserve input tokens, including schema overhead.
        input_bound = len(json.dumps(messages,ensure_ascii=False).encode())+len(json.dumps(schema.model_json_schema()).encode())+512
        output_bound = 1200 if schema.__name__ == 'Claims' else 256
        def dispatch():
            data = self.nebius.chat(messages,max_tokens=output_bound,response_format={'type':'json_schema','json_schema':{
                'name':schema.__name__,'strict':True,'schema':schema.model_json_schema()}})
            try:
                value = schema.model_validate_json(data['choices'][0]['message']['content'])
            except (KeyError,IndexError,TypeError,ValidationError):
                raise ProviderError('nebius','invalid_structured_output') from None
            return value,data.get('usage',{})
        value, usage = await self.invoke(dispatch,dict(model_calls=1,input_tokens=input_bound,output_tokens=output_bound),repair=True)
        # Reservation remains charged even on failure; record only numeric safe usage.
        self.usage.append({k:v for k,v in usage.items() if k in ('prompt_tokens','completion_tokens','total_tokens') and isinstance(v,int) and v>=0})
        return value


class ScopedBudget:
    """Fixed company allowance plus global budget; checks are atomic before mutation."""
    def __init__(self,parent,limits):
        self.parent,self.limits,self.used=parent,limits,{}

    def check(self):
        self.parent.check()

    def reserve(self,**amounts):
        self.check()
        if any(self.used.get(k,0)+v>self.limits[k] for k,v in amounts.items()):
            raise BudgetExceeded('company_budget_exhausted')
        self.parent.reserve(**amounts)
        for k,v in amounts.items(): self.used[k]=self.used.get(k,0)+v
