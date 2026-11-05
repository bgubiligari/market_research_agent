"""Bounded HTTP adapters. No upstream bodies or credentials enter public errors.

Clients are injected for tests and must be closed by their owner. Fixed upstream hosts,
no redirects, and no automatic retries: the future run budget owns retry decisions.
"""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import socket
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from .settings import Settings


class ProviderError(Exception):
    def __init__(self, provider: str, code: str, retry_after: str | None = None):
        super().__init__(f"{provider}: {code}")
        self.code = code
        self.retry_after = retry_after


class SearchProvider(Protocol):
    def search(self, query: str, *, news_days: int | None = None) -> dict: ...
    def extract(self, urls: list[str]) -> dict: ...


class InferenceProvider(Protocol):
    def structured(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel: ...


def public_url(url: str) -> None:
    """Validate user-supplied extraction URLs; Tavily performs the actual fetch.

    We never follow extracted links locally. Tavily's redirect/DNS behavior remains
    an upstream trust boundary, rather than a guarantee made by this validator.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Extraction requires a public HTTPS URL")
    if parsed.port not in (None, 443):
        raise ValueError("Nonstandard extraction port")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Nonpublic extraction address")
    except OSError:
        raise ValueError("Extraction host could not be resolved") from None


class HTTPProvider:
    def __init__(self, client: httpx.Client, settings: Settings, name: str):
        self.client, self.settings, self.name = client, settings, name

    def request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self.client.request(method, url, timeout=self.settings.provider_timeout_seconds,
                                           follow_redirects=False, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                raise ProviderError(self.name, "temporarily_unavailable", response.headers.get("retry-after"))
            if not 200 <= response.status_code < 300:
                raise ProviderError(self.name, "authentication_failed" if response.status_code in (401, 403) else "request_failed")
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (httpx.HTTPError, ValueError):
            raise ProviderError(self.name, "invalid_response_or_transport") from None


class Tavily(HTTPProvider):
    def __init__(self, client: httpx.Client, settings: Settings):
        super().__init__(client, settings, "tavily")

    def _post(self, endpoint: str, body: dict) -> dict:
        if not self.settings.tavily_api_key:
            raise ProviderError(self.name, "not_configured")
        return self.request("POST", f"https://api.tavily.com/{endpoint}", json=body,
                            headers={"Authorization": f"Bearer {self.settings.tavily_api_key.get_secret_value()}"})

    def search(self, query: str, *, news_days: int | None = None) -> dict:
        if not query.strip() or len(query) > 2000:
            raise ValueError("Invalid search query")
        body = dict(query=query, max_results=5, search_depth="basic", include_answer=False,
                    include_raw_content=False, include_usage=True, include_published_date=True, topic="general")
        if news_days is not None:
            if not 1 <= news_days <= 365:
                raise ValueError("Invalid news lookback")
            today=datetime.now(timezone.utc).date()
            body.update(topic="news", start_date=str(today-timedelta(days=news_days)),
                        end_date=str(today), filter_by_published_date=True)
        data = self._post("search", body)
        if not isinstance(data.get("results"), list):
            raise ProviderError(self.name, "invalid_results")
        return data

    def extract(self, urls: list[str]) -> dict:
        if not 1 <= len(urls) <= 5:
            raise ValueError("Extract one to five URLs")
        for url in urls:
            public_url(url)
        data = self._post("extract", dict(urls=urls, extract_depth="basic", include_usage=True))
        if not isinstance(data.get("results"), list) or not isinstance(data.get("failed_results", []), list):
            raise ProviderError(self.name, "invalid_results")
        return data


class Nebius(HTTPProvider):
    def __init__(self, client: httpx.Client, settings: Settings):
        super().__init__(client, settings, "nebius")

    def chat(self, messages: list[dict], **options) -> dict:
        if not self.settings.nebius_api_key or not self.settings.nebius_model:
            raise ProviderError(self.name, "not_configured")
        return self.request("POST", "https://api.tokenfactory.nebius.com/v1/chat/completions",
                            headers={"Authorization": f"Bearer {self.settings.nebius_api_key.get_secret_value()}"},
                            json={"model": self.settings.nebius_model, "messages": messages,
                                  "temperature": 0, "max_tokens": 512, **options})

    def structured(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        data = self.chat(messages, response_format={"type": "json_schema", "json_schema": {
            "name": schema.__name__, "strict": True, "schema": schema.model_json_schema()}})
        try:
            return schema.model_validate_json(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, ValidationError):
            raise ProviderError(self.name, "invalid_structured_output") from None

    def capability_check(self) -> dict:
        """Two explicit paid calls; validates actual arguments and structured content."""
        class Probe(BaseModel):
            model_config = {"extra": "forbid"}
            ok: bool
        structured = self.structured([{"role": "user", "content": 'Return {"ok": true}.'}], Probe)
        tool = {"type": "function", "function": {"name": "probe", "description": "Capability probe",
                "parameters": {"type": "object", "properties": {"ok": {"type": "boolean"}},
                               "required": ["ok"], "additionalProperties": False}}}
        response = self.chat([{"role": "user", "content": "Call probe with ok true."}],
                             tools=[tool], tool_choice={"type": "function", "function": {"name": "probe"}})
        try:
            call = response["choices"][0]["message"]["tool_calls"][0]["function"]
            valid = call["name"] == "probe" and json.loads(call["arguments"]) == {"ok": True}
        except (KeyError, IndexError, TypeError, ValueError):
            valid = False
        if not structured.ok or not valid:
            raise ProviderError(self.name, "capability_check_failed")
        return {"model": self.settings.nebius_model, "structured_output": True, "tool_calls": True}
