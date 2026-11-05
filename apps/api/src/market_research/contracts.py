"""Versioned public data contracts. These do not execute agents or calculate financials."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

Text = Annotated[str, Field(min_length=1, max_length=2000)]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
Number = Annotated[Decimal, Field(allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RunStatus(StrEnum):
    QUEUED = "queued"
    RESOLVING = "resolving"
    AWAITING_REVIEW = "awaiting_review"
    RESEARCHING = "researching"
    VALIDATING = "validating"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ResearchRequest(Contract):
    target: Annotated[str, Field(min_length=1, max_length=300)]
    competitors: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list, max_length=3
    )
    discovery_mode: bool = False
    geography: Text | None = None
    focus: Text | None = None
    news_lookback_days: int = Field(default=90, ge=1, le=365)

    @model_validator(mode="after")
    def comparison_set(self) -> Self:
        if self.discovery_mode:
            if self.competitors:
                raise ValueError("Discovery mode requires no supplied competitors")
        elif len(self.competitors) != 3:
            raise ValueError("Supply exactly three competitors or enable discovery mode")
        normalized = [x.casefold() for x in [self.target, *self.competitors]]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Target and competitor inputs must be distinct")
        return self


class CompanyIdentity(Contract):
    company_id: Identifier
    legal_name: Text
    website: HttpUrl
    ticker: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    cik: Annotated[str, Field(pattern=r"^\d{10}$")] | None = None
    aliases: list[Text] = Field(default_factory=list)
    resolution_source_ids: list[Identifier] = Field(min_length=1)


class ConfirmedPlan(Contract):
    plan_version: int = Field(ge=1)
    target: CompanyIdentity
    competitors: list[CompanyIdentity] = Field(min_length=3, max_length=3)
    geography: Text | None = None
    focus: Text | None = None
    news_lookback_days: int = Field(ge=1, le=365)

    @model_validator(mode="after")
    def unique_entities(self) -> Self:
        entities = [self.target, *self.competitors]
        for key in ("company_id", "cik"):
            values = [getattr(x, key) for x in entities if getattr(x, key) is not None]
            if len(values) != len(set(values)):
                raise ValueError(f"Confirmed companies must have distinct {key} values")
        return self


class EvidenceSource(Contract):
    source_id: Identifier
    company_id: Identifier
    url: HttpUrl
    title: Text
    publisher: Text
    source_type: Literal["official", "filing", "news", "other"]
    published_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime
    excerpt: Annotated[str, Field(min_length=1, max_length=12000)]


class Finding(Contract):
    company_id: Identifier
    field: Text
    statement: Text
    source_ids: list[Identifier] = Field(default_factory=list)
    basis: Literal["observed", "inferred"]
    evidence_status: Literal["supported", "conflicting", "missing", "not_applicable"]
    limitations: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def grounded_claim(self) -> Self:
        if self.evidence_status in {"supported", "conflicting"} and not self.source_ids:
            raise ValueError("Supported or conflicting claims require evidence sources")
        if self.evidence_status in {"missing", "conflicting"} and not self.limitations:
            raise ValueError("Missing or conflicting evidence requires an explanation")
        return self


class FiscalPeriod(Contract):
    start: date
    end: date
    fiscal_year: int = Field(ge=1900, le=2200)

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if self.start >= self.end:
            raise ValueError("Period start must precede end")
        return self


class FinancialFact(Contract):
    fact_id: Identifier
    company_id: Identifier
    concept: Text
    value: Number
    unit: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    period: FiscalPeriod
    form: Text
    filing_date: date
    accession: Text
    source_url: HttpUrl


class MetricName(StrEnum):
    REVENUE = "revenue"
    REVENUE_GROWTH = "revenue_growth"
    GROSS_MARGIN = "gross_margin"
    OPERATING_MARGIN = "operating_margin"
    OPERATING_CASH_FLOW_GROWTH = "operating_cash_flow_growth"


class MetricBreakdown(Contract):
    current_amount: Number
    prior_amount: Number
    absolute_change: Number
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class FinancialMetric(Contract):
    company_id: Identifier
    metric: MetricName
    value: Number | None
    unit: Annotated[str, Field(pattern=r"^(percent|[A-Z]{3})$")]
    period: FiscalPeriod
    input_fact_ids: list[Identifier] = Field(default_factory=list)
    breakdown: MetricBreakdown | None = None
    formula_version: Literal["1.0"] = "1.0"
    status: Literal["available", "unavailable", "not_meaningful"]
    reason: Text | None = None

    @model_validator(mode="after")
    def consistent_metric(self) -> Self:
        if self.status == "available":
            if self.value is None or not self.input_fact_ids:
                raise ValueError("Available metrics require a value and input facts")
        elif self.value is not None or self.reason is None:
            raise ValueError("Unavailable metrics require a null value and explanation")
        if self.metric == MetricName.REVENUE:
            if self.unit == "percent":
                raise ValueError("Revenue must use a currency unit")
        elif self.unit != "percent":
            raise ValueError("Growth and margin metrics must use percent")
        return self


class AnalysisReport(Contract):
    schema_version: Literal["1.0"] = "1.0"
    as_of: AwareDatetime
    status: Literal["completed", "partial"]
    plan: ConfirmedPlan
    briefing: list[Finding]
    findings: list[Finding]
    financial_facts: list[FinancialFact]
    financial_metrics: list[FinancialMetric]
    sources: list[EvidenceSource]
    warnings: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        companies = {self.plan.target.company_id, *(x.company_id for x in self.plan.competitors)}
        sources = {x.source_id: x for x in self.sources}
        facts = {x.fact_id: x for x in self.financial_facts}
        if len(sources) != len(self.sources) or len(facts) != len(self.financial_facts):
            raise ValueError("Evidence and fact IDs must be unique")
        for record in [*self.sources, *self.financial_facts, *self.financial_metrics,
                       *self.briefing, *self.findings]:
            if record.company_id not in companies:
                raise ValueError("Report references a company outside the confirmed plan")
        for company in [self.plan.target, *self.plan.competitors]:
            if not set(company.resolution_source_ids) <= sources.keys():
                raise ValueError("Company resolution references an unknown source")
            if any(sources[sid].company_id != company.company_id for sid in company.resolution_source_ids):
                raise ValueError("Company resolution references another company's source")
        for finding in [*self.briefing, *self.findings]:
            if not set(finding.source_ids) <= sources.keys():
                raise ValueError("Finding references an unknown source")
            if any(sources[sid].company_id != finding.company_id for sid in finding.source_ids):
                raise ValueError("Finding references another company's source")
        for metric in self.financial_metrics:
            for fact_id in metric.input_fact_ids:
                if fact_id not in facts or facts[fact_id].company_id != metric.company_id:
                    raise ValueError("Metric references an unknown or another company's fact")
        if self.status == "partial" and not self.warnings:
            raise ValueError("Partial reports require a coverage warning")
        return self
