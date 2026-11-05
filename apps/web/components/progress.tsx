import type { Snapshot } from "../lib/contracts";
import { Icon } from "./icon";
const steps = [
  ["Resolve identities", "Match companies and official websites"],
  ["Review plan", "Your approval before company research"],
  ["Collect & analyze", "Annual filings, web evidence and recent news"],
  ["Validate evidence", "Check coverage, dates and citations"],
  ["Compile briefing", "Bring the supported findings together"],
];
export const stageLabels: Record<string, string> = {
  queued: "Waiting to start",
  financials: "Checking financial coverage",
  collecting: "Collecting web & news evidence",
  analyzing: "Extracting cited findings",
  followup: "Checking evidence gaps",
  completed: "Research complete",
  partial: "Partial evidence",
  failed: "Branch failed",
};
export function Progress({
  snapshot,
  connection,
}: {
  snapshot: Snapshot | null;
  connection: string;
}) {
  const status = snapshot?.status || "queued";
  const terminal = [
    "completed",
    "partial",
    "failed",
    "cancelled",
    "expired",
  ].includes(status);
  const step =
    !snapshot || ["cancelled", "failed", "expired"].includes(status)
      ? -1
      : ["queued", "resolving"].includes(status)
        ? 0
        : status === "awaiting_review"
          ? 1
          : status === "researching"
            ? 2
            : status === "validating"
              ? 3
              : 4;
  const companies = snapshot?.plan
    ? [snapshot.plan.target, ...snapshot.plan.competitors]
    : [];
  return (
    <>
      <div className="section-head">
        <div>
          <span className="eyebrow">LIVE WORKFLOW</span>
          <h2 className="status-title">
            {snapshot ? status.replaceAll("_", " ") : "Your research pipeline"}
          </h2>
        </div>
        <span
          className={`badge ${status === "awaiting_review" ? "amber" : status === "partial" ? "amber" : status === "failed" ? "red" : "teal"}`}
        >
          {connection}
        </span>
      </div>
      <ol className="pipeline">
        {steps.map(([title, description], i) => {
          const done =
            status === "completed" || status === "partial" || i < step;
          const current = i === step && !terminal;
          return (
            <li
              key={title}
              className={done ? "done" : current ? "current" : ""}
            >
              <span className="step-marker">
                {done ? (
                  <Icon name="check" size={15} />
                ) : (
                  String(i + 1).padStart(2, "0")
                )}
              </span>
              <div>
                <strong>{title}</strong>
                <p>{description}</p>
              </div>
              {current && <span className="live-dot" />}
            </li>
          );
        })}
      </ol>
      {companies.length > 0 && (
        <section aria-label="Company progress" className="company-progress">
          <div className="section-head">
            <h3>Company research</h3>
            <span className="muted">Up to 2 at a time</span>
          </div>
          {companies.map((c, i) => {
            const p = snapshot?.company_progress?.[c.company_id];
            return (
              <div className="company-progress-row" key={c.company_id}>
                <span className={`company-avatar color-${i}`}>
                  {c.ticker?.slice(0, 2) || c.legal_name.slice(0, 2)}
                </span>
                <div>
                  <strong>{c.ticker || c.legal_name}</strong>
                  <small>
                    {p
                      ? ["cancelled", "failed", "expired"].includes(status) &&
                        !["completed", "partial", "failed"].includes(p.stage)
                        ? "Stopped"
                        : stageLabels[p.stage] || p.stage
                      : status === "awaiting_review"
                        ? "Awaiting your approval"
                        : "Not started"}
                  </small>
                </div>
                <span className="muted">
                  {p?.sources_collected !== undefined
                    ? `${p.sources_collected} source${p.sources_collected === 1 ? "" : "s"}`
                    : "—"}
                </span>
              </div>
            );
          })}
        </section>
      )}
      {(snapshot?.activity?.length || 0) > 0 && (
        <section className="activity" aria-label="Research activity">
          <h3>
            Activity feed <span className="badge neutral">Run events</span>
          </h3>
          <ul>
            {snapshot!
              .activity!.slice()
              .reverse()
              .slice(0, 10)
              .map((a, i) => (
                <li key={`${a.at}-${i}`}>
                  <span className="activity-dot" />
                  <div>
                    <strong>
                      {companies.find((c) => c.company_id === a.company_id)
                        ?.ticker ||
                        companies.find((c) => c.company_id === a.company_id)
                          ?.legal_name}
                    </strong>
                    <p>
                      {stageLabels[a.stage] || a.stage}
                      {a.sources_collected !== undefined
                        ? ` · ${a.sources_collected} collected sources`
                        : ""}
                      {a.search_attempts !== undefined
                        ? ` · ${a.search_attempts} search attempts`
                        : ""}
                    </p>
                  </div>
                  <time>
                    {new Date(a.at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </li>
              ))}
          </ul>
        </section>
      )}
    </>
  );
}
