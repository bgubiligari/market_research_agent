"use client";
import { useState } from "react";
import type { Report, Finding, Source } from "../lib/contracts";
import { fieldNames, fields, metricValue } from "../lib/presentation";
import { FinancialPanel } from "./financial-panel";
import { EvidenceDrawer, type EvidenceSelection } from "./evidence-drawer";
import { Icon } from "./icon";
const tabs = [
  "Overview",
  "Companies",
  "Comparison",
  "Financials",
  "Recent developments",
  "Sources",
];
export function ReportView({
  report,
  runStatus,
}: {
  report: Report;
  runStatus?: string;
}) {
  const [tab, setTab] = useState("Overview");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const [query, setQuery] = useState("");
  const [companyFilter, setCompanyFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [citedOnly, setCitedOnly] = useState(false);
  const companies = [report.plan.target, ...report.plan.competitors];
  const cited = new Set(
    [...report.findings, ...report.briefing].flatMap((f) => f.source_ids),
  );
  const covered = companies.reduce(
    (n, c) =>
      n +
      fields.filter((field) =>
        report.findings.some(
          (f) =>
            f.company_id === c.company_id &&
            f.field === field &&
            ["supported", "not_applicable"].includes(f.evidence_status),
        ),
      ).length,
    0,
  );
  const missing = companies.flatMap((c) =>
    fields
      .filter(
        (field) =>
          !report.findings.some(
            (f) =>
              f.company_id === c.company_id &&
              f.field === field &&
              ["supported", "not_applicable"].includes(f.evidence_status),
          ),
      )
      .map((field) => ({ company: c, field })),
  );
  function openSource(id: string) {
    const source = report.sources.find((s) => s.source_id === id);
    if (source) setEvidence({ kind: "source", source });
  }
  function citations(f: Finding) {
    return (
      <span className="citations">
        {f.source_ids.map((id) => (
          <button
            aria-label={`View source ${report.sources.findIndex((s) => s.source_id === id) + 1}`}
            key={id}
            onClick={() => openSource(id)}
          >
            [{report.sources.findIndex((s) => s.source_id === id) + 1}]
          </button>
        ))}
      </span>
    );
  }
  function finding(f: Finding, i = 0) {
    return (
      <article
        className={`finding ${f.evidence_status === "missing" ? "missing-finding" : ""}`}
        key={`${f.company_id}-${f.field}-${i}`}
      >
        <div className="finding-meta">
          <span
            className={`badge ${f.evidence_status === "supported" ? "neutral" : f.evidence_status === "missing" || f.evidence_status === "conflicting" ? "amber" : "neutral"}`}
          >
            {f.evidence_status === "supported"
              ? "Source-backed"
              : f.evidence_status.replaceAll("_", " ")}
          </span>
          <span>
            {f.basis === "inferred" ? "Inferred interpretation" : "Observation"}
          </span>
        </div>
        <p>
          {f.statement} {citations(f)}
        </p>
        {f.limitations.map((l, j) => (
          <p className="micro" key={j}>
            {l}
          </p>
        ))}
      </article>
    );
  }
  function sourceCard(s: Source) {
    return (
      <button
        className="source-card"
        key={s.source_id}
        onClick={() => setEvidence({ kind: "source", source: s })}
      >
        <span className="source-icon">
          <Icon name={s.source_type === "filing" ? "file" : "link"} />
        </span>
        <span className="source-card-main">
          <span className="eyebrow">
            {companies.find((c) => c.company_id === s.company_id)?.ticker ||
              companies.find((c) => c.company_id === s.company_id)
                ?.legal_name}{" "}
            · {s.source_type}
          </span>
          <strong>{s.title}</strong>
          <small>
            {s.publisher} ·{" "}
            {s.published_at
              ? `Published ${new Date(s.published_at).toLocaleDateString()}`
              : "Undated"}{" "}
            ·{" "}
            {cited.has(s.source_id)
              ? "Cited in findings"
              : "Collected evidence"}
          </small>
        </span>
        <Icon name="chevron" size={17} />
      </button>
    );
  }
  return (
    <section aria-label="Research report" className="report">
      <div className="report-header">
        <div>
          <div className="breadcrumb">
            Research briefing <Icon name="chevron" size={12} />
            {report.plan.target.ticker || report.plan.target.legal_name}
          </div>
          <h1>
            {report.plan.target.ticker || report.plan.target.legal_name}{" "}
            <span className="heading-light">& the competitive landscape</span>
          </h1>
          <div className="report-meta">
            <span
              className={`badge ${report.status === "partial" ? "amber" : "teal"}`}
            >
              {report.status === "partial"
                ? "Partial report"
                : "Complete report"}
            </span>
            <span>As of {new Date(report.as_of).toLocaleString()}</span>
            <span>{report.plan.news_lookback_days}-day news window</span>
          </div>
        </div>
        <span className="edition">SOURCE-BACKED RESEARCH</span>
      </div>
      {runStatus === "cancelled" && (
        <p className="notice">
          Run cancelled. This briefing contains only evidence retained before
          cancellation.
        </p>
      )}
      {report.warnings.some((w) => w.includes("OFFLINE TEST")) && (
        <p className="notice">
          OFFLINE TEST fixture report. Not live research.
        </p>
      )}
      <div className="report-stats">
        <div>
          <Icon name="users" />
          <strong>4</strong>
          <span>Companies compared</span>
        </div>
        <div>
          <Icon name="check" />
          <strong>
            {covered}
            <small> / {companies.length * fields.length}</small>
          </strong>
          <span>Research fields covered</span>
        </div>
        <div>
          <Icon name="chart" />
          <strong>
            {
              report.financial_metrics.filter((m) => m.status === "available")
                .length
            }
            <small> / {companies.length * 15}</small>
          </strong>
          <span>Annual financial values</span>
        </div>
        <div>
          <Icon name="link" />
          <strong>{report.sources.length}</strong>
          <span>Collected sources · {cited.size} cited</span>
        </div>
      </div>
      <nav className="report-tabs" aria-label="Report sections">
        {tabs.map((t) => (
          <button
            key={t}
            aria-current={tab === t ? "page" : undefined}
            onClick={() => setTab(t)}
          >
            {t}
            {t === "Sources" && <span>{report.sources.length}</span>}
          </button>
        ))}
      </nav>
      <div className="report-body">
        {tab === "Overview" && (
          <>
            <div className="overview-layout">
              <section>
                <div className="section-head">
                  <div>
                    <span className="eyebrow">COMPETITIVE BRIEFING</span>
                    <h2>The companies at a glance</h2>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => setTab("Comparison")}
                  >
                    Compare side by side <Icon name="arrow" size={15} />
                  </button>
                </div>
                <p className="muted">
                  Cited positioning and differentiation, compiled from company
                  research. Interpretations require source review.
                </p>
                <div className="overview-cards">
                  {companies.map((c, i) => {
                    const statement =
                      report.briefing.find(
                        (f) =>
                          f.company_id === c.company_id &&
                          f.field === "positioning",
                      ) ||
                      report.briefing.find(
                        (f) => f.company_id === c.company_id,
                      );
                    const revenue = report.financial_metrics
                      .filter(
                        (m) =>
                          m.company_id === c.company_id &&
                          m.metric === "revenue",
                      )
                      .sort((a, b) =>
                        b.period.end.localeCompare(a.period.end),
                      )[0];
                    return (
                      <article className="company-summary" key={c.company_id}>
                        <div className="section-head">
                          <span className={`company-avatar color-${i}`}>
                            {c.ticker?.slice(0, 2) || c.legal_name.slice(0, 2)}
                          </span>
                          <span className="eyebrow">
                            {i === 0 ? "TARGET" : "COMPETITOR"}
                          </span>
                        </div>
                        <h3>{c.legal_name}</h3>
                        <div className="summary-revenue">
                          <strong>{metricValue(revenue, true)}</strong>
                          <span>
                            {revenue
                              ? `FY${revenue.period.fiscal_year} revenue`
                              : "Revenue unavailable"}
                          </span>
                        </div>
                        {statement ? (
                          <p className="summary-statement">
                            {statement.statement} {citations(statement)}
                          </p>
                        ) : (
                          <p className="missing">
                            Positioning evidence is unavailable.
                          </p>
                        )}
                        <div className="summary-footer">
                          <span>
                            {
                              fields.filter((field) =>
                                report.findings.some(
                                  (f) =>
                                    f.company_id === c.company_id &&
                                    f.field === field &&
                                    ["supported", "not_applicable"].includes(
                                      f.evidence_status,
                                    ),
                                ),
                              ).length
                            }
                            /6 fields covered
                          </span>
                          <button
                            className="text-button"
                            onClick={() => {
                              setCompanyFilter(c.company_id);
                              setTab("Companies");
                            }}
                          >
                            Profile <Icon name="arrow" size={13} />
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
              <aside className="coverage-card">
                <span className="eyebrow">EVIDENCE COVERAGE</span>
                <h3>
                  {missing.length
                    ? "What still needs evidence"
                    : "Required coverage complete"}
                </h3>
                <p className="muted">
                  {missing.length
                    ? "These gaps remain explicit in the report."
                    : "All required fields have supported or not-applicable evidence statuses."}
                </p>
                {missing.map(({ company, field }) => (
                  <div
                    className="coverage-gap"
                    key={`${company.company_id}-${field}`}
                  >
                    <span className="gap-dot" />
                    <div>
                      <strong>{company.ticker || company.legal_name}</strong>
                      <p>{fieldNames[field]}</p>
                    </div>
                  </div>
                ))}
                <p className="micro">
                  Coverage measures availability, not a confidence score or
                  independent proof of a claim.
                </p>
                <button
                  className="text-button"
                  onClick={() => setTab("Sources")}
                >
                  Review evidence <Icon name="arrow" size={14} />
                </button>
              </aside>
            </div>
            <section className="overview-financial-prompt">
              <Icon name="chart" size={23} />
              <div>
                <h3>Put the research in financial context</h3>
                <p>
                  Revenue, growth, gross margin, operating margin and operating
                  cash flow growth.
                </p>
              </div>
              <button
                className="button outline"
                onClick={() => setTab("Financials")}
              >
                Explore financials <Icon name="arrow" size={15} />
              </button>
            </section>
          </>
        )}
        {tab === "Companies" && (
          <>
            <div className="section-head">
              <div>
                <h2>Company profiles</h2>
                <p className="muted">
                  Evidence status and citations stay attached to every finding.
                </p>
              </div>
              <label>
                <span className="sr-only">Filter companies</span>
                <select
                  value={companyFilter}
                  onChange={(e) => setCompanyFilter(e.target.value)}
                >
                  <option value="all">All companies</option>
                  {companies.map((c) => (
                    <option key={c.company_id} value={c.company_id}>
                      {c.ticker || c.legal_name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="profiles">
              {companies
                .filter(
                  (c) =>
                    companyFilter === "all" || companyFilter === c.company_id,
                )
                .map((c, i) => (
                  <section className="profile" key={c.company_id}>
                    <div className="profile-heading">
                      <span
                        className={`company-avatar color-${companies.indexOf(c)}`}
                      >
                        {c.ticker?.slice(0, 2) || c.legal_name.slice(0, 2)}
                      </span>
                      <div>
                        <h3>{c.legal_name}</h3>
                        <span className="muted">
                          {c.ticker || "No ticker"} ·{" "}
                          {c.cik
                            ? `CIK ${c.cik}`
                            : "SEC financial coverage unconfirmed"}
                        </span>
                      </div>
                    </div>
                    {fields
                      .filter((f) => f !== "recent_developments")
                      .map((field) => (
                        <div className="profile-field" key={field}>
                          <h4>{fieldNames[field]}</h4>
                          {report.findings
                            .filter(
                              (f) =>
                                f.company_id === c.company_id &&
                                f.field === field,
                            )
                            .map(finding)}
                          {!report.findings.some(
                            (f) =>
                              f.company_id === c.company_id &&
                              f.field === field,
                          ) && (
                            <p className="missing">
                              No accepted evidence for this field.
                            </p>
                          )}
                        </div>
                      ))}
                  </section>
                ))}
            </div>
          </>
        )}
        {tab === "Comparison" && (
          <>
            <div className="section-head">
              <div>
                <h2>Side-by-side comparison</h2>
                <p className="muted">
                  Read the same dimension across all four companies. No inferred
                  rankings or scores.
                </p>
              </div>
            </div>
            <div className="table-wrap comparison-wrap">
              <table className="comparison-table">
                <caption>Source-backed company research</caption>
                <thead>
                  <tr>
                    <th>Research dimension</th>
                    {companies.map((c, i) => (
                      <th key={c.company_id}>
                        <span className={`company-dot color-${i}`} />
                        {c.ticker || c.legal_name}
                        <small>
                          {i === 0 ? "Target company" : "Competitor"}
                        </small>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {fields.map((field) => (
                    <tr key={field}>
                      <th>{fieldNames[field]}</th>
                      {companies.map((c) => (
                        <td key={c.company_id}>
                          {report.findings
                            .filter(
                              (f) =>
                                f.company_id === c.company_id &&
                                f.field === field,
                            )
                            .map(finding)}
                          {!report.findings.some(
                            (f) =>
                              f.company_id === c.company_id &&
                              f.field === field,
                          ) && (
                            <span className="missing">
                              No accepted evidence
                            </span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {tab === "Financials" && (
          <FinancialPanel
            report={report}
            onMetric={(metric) => setEvidence({ kind: "metric", metric })}
          />
        )}
        {tab === "Recent developments" && (
          <>
            <div className="section-head">
              <div>
                <h2>Recent developments</h2>
                <p className="muted">
                  Only accepted findings supported by dated evidence in the
                  requested window.
                </p>
              </div>
            </div>
            <div className="timeline">
              {report.findings
                .filter((f) => f.field === "recent_developments")
                .sort((a, b) => {
                  const date = (f: Finding) =>
                    Math.max(
                      0,
                      ...f.source_ids.map(
                        (id) =>
                          Date.parse(
                            report.sources.find((s) => s.source_id === id)
                              ?.published_at || "",
                          ) || 0,
                      ),
                    );
                  return date(b) - date(a);
                })
                .map((f, i) => {
                  const source = report.sources.find(
                    (s) => f.source_ids.includes(s.source_id) && s.published_at,
                  );
                  return (
                    <article
                      className="timeline-entry"
                      key={`${f.company_id}-${i}`}
                    >
                      <div className="timeline-date">
                        {source?.published_at ? (
                          <>
                            <strong>
                              {new Date(source.published_at).toLocaleDateString(
                                undefined,
                                { month: "short", day: "numeric" },
                              )}
                            </strong>
                            <span>Source published</span>
                          </>
                        ) : (
                          <span>No accepted date</span>
                        )}
                      </div>
                      <div>
                        <span className="eyebrow">
                          {
                            companies.find((c) => c.company_id === f.company_id)
                              ?.legal_name
                          }
                        </span>
                        {finding(f)}
                      </div>
                    </article>
                  );
                })}
              {companies
                .filter(
                  (c) =>
                    !report.findings.some(
                      (f) =>
                        f.company_id === c.company_id &&
                        f.field === "recent_developments",
                    ),
                )
                .map((c) => (
                  <p className="notice" key={c.company_id}>
                    {c.legal_name}: Recent developments are unsupported. No
                    dated evidence accepted.
                  </p>
                ))}
            </div>
          </>
        )}
        {tab === "Sources" && (
          <>
            <div className="section-head">
              <div>
                <h2>Evidence library</h2>
                <p className="muted">
                  Collected sources are distinguished from evidence cited in
                  findings.
                </p>
              </div>
              <span className="badge neutral">
                {report.sources.length} sources
              </span>
            </div>
            <div className="source-filters">
              <label className="search-input">
                <Icon name="search" size={17} />
                <span className="sr-only">Search sources</span>
                <input
                  placeholder="Search title, publisher or excerpt"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <label>
                <span className="sr-only">Source company</span>
                <select
                  value={companyFilter}
                  onChange={(e) => setCompanyFilter(e.target.value)}
                >
                  <option value="all">All companies</option>
                  {companies.map((c) => (
                    <option value={c.company_id} key={c.company_id}>
                      {c.ticker || c.legal_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span className="sr-only">Source type</span>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                >
                  <option value="all">All source types</option>
                  {["official", "filing", "news", "other"].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={citedOnly}
                  onChange={(e) => setCitedOnly(e.target.checked)}
                />
                Cited only
              </label>
            </div>
            <div className="source-list">
              {report.sources
                .filter(
                  (s) =>
                    (companyFilter === "all" ||
                      s.company_id === companyFilter) &&
                    (typeFilter === "all" || s.source_type === typeFilter) &&
                    (!citedOnly || cited.has(s.source_id)) &&
                    `${s.title} ${s.publisher} ${s.excerpt}`
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                )
                .map(sourceCard)}
            </div>
            {!report.sources.some(
              (s) =>
                (companyFilter === "all" || s.company_id === companyFilter) &&
                (typeFilter === "all" || s.source_type === typeFilter) &&
                (!citedOnly || cited.has(s.source_id)) &&
                `${s.title} ${s.publisher} ${s.excerpt}`
                  .toLowerCase()
                  .includes(query.toLowerCase()),
            ) && (
              <p className="empty-inline">No sources match these filters.</p>
            )}
          </>
        )}
        <details className="report-limitations">
          <summary>
            <span>
              <Icon name="info" size={16} />
              Coverage & comparability notes
            </span>
            <span>{report.warnings.length} notes</span>
          </summary>
          {report.warnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
          <p>
            Inferred claims require human source review. Quote matching does not
            independently establish entailment. Fiscal periods, acquisitions,
            divestitures and accounting changes affect comparability.
          </p>
        </details>
      </div>
      <EvidenceDrawer
        selection={evidence}
        report={report}
        onClose={() => setEvidence(null)}
      />
    </section>
  );
}
