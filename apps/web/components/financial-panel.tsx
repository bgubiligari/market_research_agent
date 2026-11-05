"use client";
import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { Report, Metric } from "../lib/contracts";
import { chartData } from "../lib/financials";
import { metricNames, metricValue, companyColors } from "../lib/presentation";
import { Icon } from "./icon";
export function FinancialPanel({
  report,
  onMetric,
}: {
  report: Report;
  onMetric: (m: Metric) => void;
}) {
  const [metric, setMetric] = useState("revenue");
  const companies = [report.plan.target, ...report.plan.competitors];
  const selected = report.financial_metrics.filter((m) => m.metric === metric);
  const units = [...new Set(selected.map((m) => m.unit))];
  function latest(cid: string, name: string) {
    return report.financial_metrics
      .filter((m) => m.company_id === cid && m.metric === name)
      .sort((a, b) => b.period.end.localeCompare(a.period.end))[0];
  }
  return (
    <>
      <div className="section-head">
        <div>
          <h2>Financial comparison</h2>
          <p className="muted">
            Reported annual figures. Latest fiscal periods differ by company.
          </p>
        </div>
        <span className="badge neutral">Calculated in Python</span>
      </div>
      <div className="table-wrap">
        <table className="latest-table">
          <caption>
            Latest reported fiscal year · click a value for filing evidence
          </caption>
          <thead>
            <tr>
              <th>Financial metric</th>
              {companies.map((c, i) => (
                <th key={c.company_id}>
                  <span className={`company-dot color-${i}`} />
                  {c.ticker || c.legal_name}
                  <small>
                    {latest(c.company_id, "revenue")
                      ? `FY${latest(c.company_id, "revenue").period.fiscal_year} · ends ${latest(c.company_id, "revenue").period.end}`
                      : "No annual evidence"}
                  </small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(metricNames).map(([key, name]) => (
              <tr key={key}>
                <th>{name}</th>
                {companies.map((c) => {
                  const m = latest(c.company_id, key);
                  return (
                    <td key={c.company_id}>
                      {m ? (
                        <button
                          className="metric-button"
                          onClick={() => onMetric(m)}
                        >
                          {metricValue(m, true)}
                          <Icon name="link" size={12} />
                        </button>
                      ) : (
                        <span className="missing">Unavailable</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="chart-card">
        <div className="section-head">
          <div>
            <span className="eyebrow">ANNUAL TRENDS</span>
            <h3>{metricNames[metric]}</h3>
          </div>
          <label className="metric-select">
            <span className="sr-only">Financial metric</span>
            <select value={metric} onChange={(e) => setMetric(e.target.value)}>
              {Object.entries(metricNames).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {units.map((unit) => (
          <div className="chart" key={unit}>
            <span className="axis-note">
              {unit === "percent"
                ? "Percent (%)"
                : `${unit} · base currency, displayed in billions where applicable`}
            </span>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart
                data={chartData(
                  report.financial_metrics,
                  companies.map((c) => c.company_id),
                  metric,
                  unit,
                )}
                margin={{ left: 6, right: 18, top: 28, bottom: 8 }}
              >
                <CartesianGrid
                  strokeDasharray="3 4"
                  vertical={false}
                  stroke="#e4e9ee"
                />
                <XAxis
                  dataKey="year"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: "#7a8797" }}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={66}
                  tick={{ fontSize: 11, fill: "#7a8797" }}
                  tickFormatter={(n) =>
                    Math.abs(n) >= 1e9
                      ? `${(n / 1e9).toFixed(1)}bn`
                      : Number(n).toLocaleString()
                  }
                />
                <Tooltip
                  content={({ active, label }) =>
                    active ? (
                      <div className="chart-tooltip">
                        <strong>
                          FY{label} · {unit}
                        </strong>
                        {selected
                          .filter(
                            (m) =>
                              m.unit === unit &&
                              m.period.fiscal_year === Number(label),
                          )
                          .map((m) => (
                            <p key={m.company_id}>
                              {companies.find(
                                (c) => c.company_id === m.company_id,
                              )?.ticker || m.company_id}
                              : {metricValue(m)}
                              <br />
                              <span className="muted">
                                {m.period.start} – {m.period.end} · filing
                                inputs below
                              </span>
                            </p>
                          ))}
                      </div>
                    ) : null
                  }
                />
                {companies.map((c, i) => (
                  <Line
                    key={c.company_id}
                    name={c.ticker || c.legal_name}
                    dataKey={c.company_id}
                    stroke={companyColors[i]}
                    strokeWidth={2.5}
                    dot={{ r: 3.5, strokeWidth: 2, fill: "#fff" }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
        {!units.length && (
          <p className="empty-inline">
            No financial evidence is available. Missing values are not plotted.
          </p>
        )}
        <div className="legend">
          {companies.map((c, i) => (
            <span key={c.company_id}>
              <span className={`company-dot color-${i}`} />
              {c.ticker || c.legal_name}
            </span>
          ))}
        </div>
        <p className="micro chart-footnote">
          No currency conversion. Missing and not-meaningful values remain gaps.
          Fiscal years do not represent a common calendar period.
        </p>
      </section>
      <details className="financial-details">
        <summary>
          <span>
            <Icon name="file" />
            Detailed annual values & filing evidence
          </span>
          <span className="badge neutral">
            {report.financial_metrics.length} values
          </span>
        </summary>
        <div className="table-wrap">
          <table>
            <caption>
              All five metrics · exact periods and source inputs
            </caption>
            <thead>
              <tr>
                <th>Company</th>
                <th>Metric</th>
                <th>Fiscal period</th>
                <th>Value / explanation</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {report.financial_metrics.map((m, i) => (
                <tr key={i}>
                  <th>
                    {companies.find((c) => c.company_id === m.company_id)
                      ?.ticker || m.company_id}
                  </th>
                  <td>{metricNames[m.metric]}</td>
                  <td>
                    FY{m.period.fiscal_year}
                    <small>
                      {m.period.start} – {m.period.end}
                    </small>
                    {(Date.parse(m.period.end) - Date.parse(m.period.start)) /
                      86400000 +
                      1 >=
                      370 && <span className="badge amber">53-week year</span>}
                  </td>
                  <td>
                    {metricValue(m)}
                    {m.reason && <p className="micro">{m.reason}</p>}
                    {m.breakdown && (
                      <p className="micro">
                        Current {m.breakdown.current_amount}; prior{" "}
                        {m.breakdown.prior_amount}; change{" "}
                        {m.breakdown.absolute_change} {m.breakdown.currency}
                      </p>
                    )}
                  </td>
                  <td>
                    <button className="text-button" onClick={() => onMetric(m)}>
                      Filing inputs <Icon name="link" size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
