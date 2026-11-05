"use client";
import { useEffect, useRef, useState } from "react";
import type { Report, Source, Metric } from "../lib/contracts";
import { safeUrl } from "../lib/client";
import { metricNames, metricValue } from "../lib/presentation";
import { Icon } from "./icon";
export type EvidenceSelection =
  { kind: "source"; source: Source } | { kind: "metric"; metric: Metric };
export function EvidenceDrawer({
  selection,
  report,
  onClose,
}: {
  selection: EvidenceSelection | null;
  report: Report;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    setCopied(false);
    if (selection && !ref.current?.open) ref.current?.showModal();
    if (!selection && ref.current?.open) ref.current?.close();
  }, [selection]);
  const companyId =
    selection?.kind === "source"
      ? selection.source.company_id
      : selection?.metric.company_id;
  const company = [report.plan.target, ...report.plan.competitors].find(
    (c) => c.company_id === companyId,
  );
  return (
    <dialog
      ref={ref}
      className="evidence-drawer"
      aria-labelledby="evidence-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="drawer-content">
        <div className="section-head">
          <span className="eyebrow">EVIDENCE DETAILS</span>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close evidence"
          >
            <Icon name="close" />
          </button>
        </div>
        <span className="badge neutral">{company?.legal_name}</span>
        {selection?.kind === "source" ? (
          <>
            <h2 id="evidence-title">{selection.source.title}</h2>
            <dl className="evidence-meta">
              <div>
                <dt>Publisher</dt>
                <dd>{selection.source.publisher}</dd>
              </div>
              <div>
                <dt>Source type</dt>
                <dd>{selection.source.source_type}</dd>
              </div>
              <div>
                <dt>Published</dt>
                <dd>
                  {selection.source.published_at
                    ? new Date(
                        selection.source.published_at,
                      ).toLocaleDateString()
                    : "Undated — not proof of recent news"}
                </dd>
              </div>
              <div>
                <dt>Retrieved</dt>
                <dd>
                  {new Date(selection.source.retrieved_at).toLocaleString()}
                </dd>
              </div>
            </dl>
            <h3>Stored source excerpt</h3>
            <blockquote>{selection.source.excerpt}</blockquote>
            <p className="micro">
              An excerpt establishes provenance. Review the original source to
              assess whether it supports the interpretation.
            </p>
            <a
              className="button primary"
              href={safeUrl(selection.source.url)}
              target="_blank"
              rel="noreferrer"
            >
              Open original source <Icon name="arrow" size={16} />
            </a>
            <button
              className="button outline"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    `${selection.source.title}. ${selection.source.publisher}. ${selection.source.url}`,
                  );
                  setCopied(true);
                } catch {
                  setCopied(false);
                }
              }}
            >
              {copied ? "Citation copied" : "Copy citation"}
            </button>
            <p className="micro" role="status">
              {copied ? "Citation copied to clipboard." : ""}
            </p>
            <p className="source-url">{selection.source.url}</p>
          </>
        ) : selection?.kind === "metric" ? (
          <>
            <h2 id="evidence-title">{metricNames[selection.metric.metric]}</h2>
            <div className="metric-evidence-value">
              {metricValue(selection.metric)}
            </div>
            <p>
              FY{selection.metric.period.fiscal_year} ·{" "}
              {selection.metric.period.start} – {selection.metric.period.end}
            </p>
            <p className="muted">
              Exact metric value: {selection.metric.value ?? "Not available"}{" "}
              {selection.metric.unit} · Python formula version 1.0
            </p>
            {selection.metric.reason && (
              <p className="notice">{selection.metric.reason}</p>
            )}
            {selection.metric.breakdown && (
              <dl className="evidence-meta">
                {Object.entries(selection.metric.breakdown).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k.replaceAll("_", " ")}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            )}
            <h3>Official filing inputs</h3>
            {selection.metric.input_fact_ids.map((id) => {
              const f = report.financial_facts.find((f) => f.fact_id === id);
              return f ? (
                <article className="filing-input" key={id}>
                  <span className="eyebrow">
                    {f.form} · FILED {f.filing_date}
                  </span>
                  <h4>{f.concept}</h4>
                  <strong>
                    {f.value} {f.unit}
                  </strong>
                  <p>
                    {f.period.start} – {f.period.end}
                  </p>
                  <p className="micro">Accession {f.accession}</p>
                  <a
                    href={safeUrl(f.source_url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open official filing ↗
                  </a>
                </article>
              ) : (
                <p key={id}>Filing input unavailable.</p>
              );
            })}
          </>
        ) : null}
      </div>
    </dialog>
  );
}
