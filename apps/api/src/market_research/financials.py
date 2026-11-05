"""Deterministic Decimal arithmetic; never substitutes missing annual evidence."""
from datetime import timedelta
from decimal import Decimal
from .contracts import FinancialFact, FinancialMetric, FiscalPeriod, MetricName


def calculate_metrics(company_id: str, period: FiscalPeriod,
                      facts: dict[str, list[FinancialFact]], currency: str = "USD") -> list[FinancialMetric]:
    def matching(role, target):
        matches = [f for f in facts.get(role, []) if f.company_id == company_id and f.unit == currency
                   and f.period.start == target.start and f.period.end == target.end
                   and 350 <= (f.period.end-f.period.start).days <= 380
                   and f.form in ("10-K", "10-K/A")]
        return matches[0] if len(matches) == 1 else None

    revenue = matching("revenue", period)
    results = []
    for metric in MetricName:
        inputs, value, reason, status, breakdown = [], None, "Required matching annual evidence is missing", "unavailable", None
        if metric == MetricName.REVENUE and revenue:
            inputs, value = [revenue], revenue.value
        elif metric in (MetricName.GROSS_MARGIN, MetricName.OPERATING_MARGIN) and revenue:
            numerator = matching("gross_profit" if metric == MetricName.GROSS_MARGIN else "operating_income", period)
            cost = matching("cost_of_sales", period) if metric == MetricName.GROSS_MARGIN and numerator is None else None
            if numerator or cost:
                inputs = [revenue, numerator or cost]
                if revenue.value > 0:
                    amount = numerator.value if numerator else revenue.value - cost.value
                    value = Decimal(100) * amount / revenue.value
                else:
                    reason = "Revenue denominator must be positive"
        elif metric in (MetricName.REVENUE_GROWTH, MetricName.OPERATING_CASH_FLOW_GROWTH):
            role = "revenue" if metric == MetricName.REVENUE_GROWTH else "ocf"
            current = matching(role, period)
            priors = [f for f in facts.get(role, []) if f.company_id == company_id and f.unit == currency
                      and f.period.end == period.start - timedelta(days=1)
                      and 350 <= (f.period.end-f.period.start).days <= 380
                      and f.form in ("10-K", "10-K/A")]
            if current and len(priors) == 1:
                prior = priors[0]
                inputs = [current, prior]
                breakdown = dict(current_amount=current.value, prior_amount=prior.value,
                                 absolute_change=current.value-prior.value, currency=currency)
                if prior.value > 0:
                    value = Decimal(100) * (current.value/prior.value - 1)
                else:
                    status, reason = "not_meaningful", "Prior annual amount must be positive for growth"
        if value is not None:
            status, reason = "available", None
        results.append(FinancialMetric(company_id=company_id, metric=metric, value=value,
            unit=currency if metric == MetricName.REVENUE else "percent", period=period,
            input_fact_ids=[f.fact_id for f in inputs], status=status, reason=reason, breakdown=breakdown))
    return results


def fiscal_warnings(periods: list[FiscalPeriod]) -> list[str]:
    """Calendar disclosures only; accounting/scope changes require filing review."""
    warnings = []
    for period in periods:
        days = (period.end - period.start).days + 1
        if days in (364, 371):
            warnings.append(f"Fiscal period ending {period.end} contains {days // 7} weeks; compare exact fiscal dates.")
    return warnings
