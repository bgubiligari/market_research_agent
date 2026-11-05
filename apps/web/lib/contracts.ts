// Wire types follow docs/contracts; Decimal values arrive as JSON strings.
export type Handle = { run_id: string; run_token: string };
export type Company = {
  company_id: string;
  legal_name: string;
  website: string;
  ticker: string | null;
  cik: string | null;
  resolution_source_ids: string[];
};
export type Plan = {
  plan_version: number;
  target: Company;
  competitors: Company[];
  geography: string | null;
  focus: string | null;
  news_lookback_days: number;
};
export type Snapshot = {
  run_id: string;
  status: string;
  plan: Plan | null;
  error: string | null;
  last_event_id: number;
  report_available: boolean;
  company_progress?: Record<string, CompanyProgress>;
  activity?: Activity[];
  budget: { reserved: Record<string, number>; limits: Record<string, number> };
};
export type Finding = {
  company_id: string;
  field: string;
  statement: string;
  source_ids: string[];
  basis: string;
  evidence_status: string;
  limitations: string[];
};
export type Period = { start: string; end: string; fiscal_year: number };
export type Metric = {
  company_id: string;
  metric: string;
  value: string | number | null;
  unit: string;
  period: Period;
  input_fact_ids: string[];
  status: string;
  reason: string | null;
  breakdown: {
    current_amount: string;
    prior_amount: string;
    absolute_change: string;
    currency: string;
  } | null;
};
export type Fact = {
  fact_id: string;
  company_id: string;
  concept: string;
  value: string;
  unit: string;
  period: Period;
  form: string;
  filing_date: string;
  accession: string;
  source_url: string;
};
export type Source = {
  source_id: string;
  company_id: string;
  url: string;
  title: string;
  publisher: string;
  source_type: string;
  published_at: string | null;
  retrieved_at: string;
  excerpt: string;
};
export type Report = {
  as_of: string;
  status: string;
  plan: Plan;
  briefing: Finding[];
  findings: Finding[];
  financial_facts: Fact[];
  financial_metrics: Metric[];
  sources: Source[];
  warnings: string[];
};
export type CompanyProgress = {
  company_id: string;
  stage: string;
  sources_collected?: number;
  search_attempts?: number;
  supported_fields?: number;
};
export type Activity = CompanyProgress & { at: string };
