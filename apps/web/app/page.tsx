"use client";
import { useEffect, useRef, useState } from "react";
import type { Handle, Snapshot, Report } from "../lib/contracts";
import {
  api,
  ApiError,
  safeUrl,
  storageKey,
  stream,
  terminal,
} from "../lib/client";
import { Button } from "../components/button";
import { Progress } from "../components/progress";
import { Icon } from "../components/icon";
import { ReportView } from "../components/report";
const demo = ["HSY", "MDLZ", "KHC", "GIS"];
export default function Home() {
  const [view, setView] = useState<"setup" | "run" | "briefing">("setup");
  const [inputs, setInputs] = useState(demo);
  const [discovery, setDiscovery] = useState(false);
  const [geography, setGeography] = useState("");
  const [focus, setFocus] = useState("");
  const [days, setDays] = useState(90);
  const [handle, setHandle] = useState<Handle | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [connection, setConnection] = useState("Connecting");
  const [retry, setRetry] = useState(0);
  const [ready, setReady] = useState<boolean | null>(null);
  const [restored, setRestored] = useState(false);
  const cursor = useRef(0);
  const openedReport = useRef(false);
  useEffect(() => {
    if (
      report &&
      ["completed", "partial"].includes(snapshot?.status || "") &&
      !openedReport.current
    ) {
      setView("briefing");
      openedReport.current = true;
    }
  }, [report, snapshot?.status]);
  const createKey = useRef<string | null>(null);
  const latest = useRef<Snapshot | null>(null);
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (
        saved &&
        typeof saved.run_id === "string" &&
        typeof saved.run_token === "string" &&
        /^[A-Za-z0-9_-]+$/.test(saved.run_id)
      ) {
        setHandle({ run_id: saved.run_id, run_token: saved.run_token });
        setView("run");
      }
    } catch {
      try {
        sessionStorage.removeItem(storageKey);
      } catch {
        /* Storage may be blocked. */
      }
    }
    setRestored(true);
    api<{ ready: boolean }>("ready")
      .then((r) => setReady(r.ready))
      .catch(() => setReady(false));
  }, []);
  useEffect(() => {
    if (!handle) return;
    const controller = new AbortController();
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    let delay = 700;
    const apply = (s: Snapshot, id = s.last_event_id) => {
      if (!alive) return;
      cursor.current = id;
      // Replayed historical events advance the cursor without regressing the UI.
      if (!latest.current || s.last_event_id >= latest.current.last_event_id) {
        latest.current = s;
        setSnapshot(s);
      }
    };
    async function reportIfAvailable(s: Snapshot) {
      if (s.report_available) {
        try {
          const r = await api<Report>(
            `runs/${handle!.run_id}/report`,
            handle!,
            undefined,
            undefined,
            controller.signal,
          );
          if (alive) setReport(r);
        } catch (e) {
          if (alive)
            setError(
              e instanceof ApiError
                ? e.message
                : "Report could not load. Retry connection.",
            );
        }
      }
    }
    async function connect() {
      try {
        setConnection("Connecting");
        const s = await api<Snapshot>(
          `runs/${handle!.run_id}`,
          handle!,
          undefined,
          undefined,
          controller.signal,
        );
        apply(s, cursor.current);
        await reportIfAvailable(s);
        if (terminal.has(s.status)) {
          setConnection("Finished");
          return;
        }
        setConnection("Connected");
        await stream(handle!, cursor.current, controller.signal, (s, id) =>
          apply(s, id),
        );
        if (!alive) return;
        if (latest.current && terminal.has(latest.current.status)) {
          setConnection("Finished");
          await reportIfAvailable(latest.current);
          return;
        }
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && [404, 410].includes(e.status)) {
          setError(e.message);
          setConnection(e.status === 410 ? "Expired" : "Unavailable");
          return;
        }
      }
      if (alive) {
        setConnection("Reconnecting · progress will replay");
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 8000);
      }
    }
    connect();
    return () => {
      alive = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [handle, retry]);
  async function create() {
    setBusy(true);
    setError("");
    createKey.current ||= crypto.randomUUID();
    try {
      const h = await api<Handle>(
        "runs",
        undefined,
        {
          target: inputs[0].trim(),
          competitors: discovery ? [] : inputs.slice(1).map((x) => x.trim()),
          discovery_mode: discovery,
          geography: geography.trim() || null,
          focus: focus.trim() || null,
          news_lookback_days: days,
        },
        createKey.current,
      );
      cursor.current = 0;
      latest.current = null;
      setHandle(h);
      setView("run");
      try {
        sessionStorage.setItem(
          storageKey,
          JSON.stringify({ run_id: h.run_id, run_token: h.run_token }),
        );
      } catch {
        setError(
          "Temporary storage unavailable. Keep this tab open to retain this run.",
        );
      }
      createKey.current = null;
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Could not create the run. Retry uses the same request key.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function command(action: "confirm" | "cancel") {
    if (!handle) return;
    setBusy(true);
    setError("");
    try {
      const s = await api<Snapshot>(
        `runs/${handle.run_id}/${action}`,
        handle,
        action === "confirm"
          ? { plan_version: snapshot?.plan?.plan_version, approved: true }
          : {},
      );
      latest.current = s;
      setSnapshot(s);
      setRetry((n) => n + 1);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Connection interrupted. Refresh status before retrying.",
      );
      setRetry((n) => n + 1);
    } finally {
      setBusy(false);
    }
  }
  function reset() {
    if (snapshot?.plan) {
      const plan = snapshot.plan;
      setInputs(
        [plan.target, ...plan.competitors].map((c) => c.ticker || c.legal_name),
      );
      setGeography(plan.geography || "");
      setFocus(plan.focus || "");
      setDays(plan.news_lookback_days);
      setDiscovery(false);
    }
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      /* Nothing is persisted. */
    }
    setHandle(null);
    setView("setup");
    openedReport.current = false;
    setSnapshot(null);
    setReport(null);
    setError("");
    latest.current = null;
    cursor.current = 0;
    createKey.current = null;
  }
  const active =
    handle &&
    (!snapshot || !terminal.has(snapshot.status)) &&
    !["Unavailable", "Expired"].includes(connection);
  const invalid =
    inputs[0].trim() === "" ||
    (!discovery && inputs.some((x) => !x.trim())) ||
    new Set(
      (discovery ? inputs.slice(0, 1) : inputs).map((x) =>
        x.trim().toLowerCase(),
      ),
    ).size !== (discovery ? 1 : 4) ||
    days < 1 ||
    days > 365;

  const plan = snapshot?.plan;
  const companies = plan ? [plan.target, ...plan.competitors] : [];
  const scopeForm = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create();
      }}
      onChange={() => {
        createKey.current = null;
      }}
    >
      <div className="section-head">
        <h2>Research setup</h2>
        <button
          className="text-button"
          type="button"
          onClick={() => {
            setInputs(demo);
            setDiscovery(false);
            createKey.current = null;
          }}
        >
          Load HSY demo
        </button>
      </div>
      <p className="muted">Define your company and three peers.</p>
      <label>
        Target company
        <input
          required
          maxLength={300}
          value={inputs[0]}
          onChange={(e) => setInputs([e.target.value, ...inputs.slice(1)])}
          placeholder="Company name or ticker"
          disabled={busy}
        />
      </label>
      <div className="field-heading">
        <span>Competitors</span>
        <span>3 peers</span>
      </div>
      {inputs.slice(1).map((value, i) => (
        <label className="peer-input" key={i}>
          <span className="sr-only">Competitor {i + 1}</span>
          <span className="peer-number">{i + 1}</span>
          <input
            required={!discovery}
            disabled={discovery || busy}
            maxLength={300}
            value={value}
            onChange={(e) =>
              setInputs(
                inputs.map((x, j) => (j === i + 1 ? e.target.value : x)),
              )
            }
            placeholder={`Competitor ${i + 1}`}
          />
        </label>
      ))}
      <label className="check">
        <input
          type="checkbox"
          checked={discovery}
          disabled={busy}
          onChange={(e) => setDiscovery(e.target.checked)}
        />
        Discover three competitors for me
      </label>
      <div className="scope-fields">
        <label>
          Recent news · days
          <input
            type="number"
            min={1}
            max={365}
            required
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </label>
        <details>
          <summary>
            Additional scope <span className="muted">Optional</span>
          </summary>
          <label>
            Geography
            <input
              maxLength={2000}
              value={geography}
              onChange={(e) => setGeography(e.target.value)}
              placeholder="e.g. United States"
            />
          </label>
          <label>
            Research focus
            <input
              maxLength={2000}
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder="e.g. brand positioning"
            />
          </label>
        </details>
      </div>
      <Button
        className="full-width"
        disabled={busy || invalid || ready !== true}
      >
        {busy ? (
          "Resolving request…"
        ) : (
          <>
            Review research plan <Icon name="arrow" size={16} />
          </>
        )}
      </Button>
      <p className="micro">
        Identity resolution uses live providers. Research starts after your
        approval.
      </p>
      {ready !== true && (
        <div className="notice" role="status">
          {ready === null
            ? "Checking local API…"
            : "Local API unavailable or credentials not configured."}
          <button
            type="button"
            className="text-button"
            onClick={() =>
              api<{ ready: boolean }>("ready")
                .then((r) => setReady(r.ready))
                .catch(() => setReady(false))
            }
          >
            Check again
          </button>
        </div>
      )}
    </form>
  );
  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="/">
          <span className="brand-mark">f.</span>
          <strong>Fieldnote</strong>
          <span className="brand-divider" />{" "}
          <span className="brand-sub">Research workspace</span>
        </a>
        <div className="header-actions">
          <span className="local">
            <span className="live-dot" /> Local session
          </span>
          {handle && active && (
            <Button
              className="mobile-stop"
              variant="outline"
              disabled={busy}
              onClick={() => command("cancel")}
            >
              Stop research
            </Button>
          )}
          {handle && !active && (
            <Button variant="outline" onClick={reset}>
              New comparison
            </Button>
          )}
        </div>
      </header>
      <div className="workspace">
        <aside className={`sidebar ${view === "setup" ? "mobile-active" : ""}`}>
          <span className="eyebrow">WORKSPACE</span>
          <nav className="workspace-nav" aria-label="Workspace">
            {(
              [
                ["setup", "grid", "Setup"],
                ["run", "play", "Run"],
                ["briefing", "file", "Briefing"],
              ] as const
            ).map(([key, icon, label]) => (
              <button
                key={key}
                aria-current={view === key ? "page" : undefined}
                disabled={key === "briefing" && !report}
                onClick={() => setView(key)}
              >
                <Icon name={icon} />
                {label}
                {key === "run" && active && <span className="live-dot" />}
                {key === "briefing" && report && (
                  <span
                    className={`badge ${report.status === "partial" ? "amber" : "teal"}`}
                  >
                    {report.status === "partial" ? "Partial" : "Ready"}
                  </span>
                )}
              </button>
            ))}
          </nav>
          <div className="sidebar-body">
            {!handle ? (
              scopeForm
            ) : (
              <>
                <div className="section-head">
                  <h2>Comparison scope</h2>
                  <Icon name="users" />
                </div>
                <div className="scope-companies">
                  {(companies.length
                    ? companies
                    : inputs.map((name, i) => ({
                        company_id: String(i),
                        legal_name: name,
                        ticker: name,
                        website: "",
                      }))
                  ).map((c, i) => (
                    <div className="scope-company" key={c.company_id}>
                      <span className={`company-avatar color-${i}`}>
                        {c.ticker?.slice(0, 2) || c.legal_name.slice(0, 2)}
                      </span>
                      <div>
                        <strong>{c.ticker || c.legal_name}</strong>
                        <small>
                          {i === 0 ? "Target company" : "Competitor"}
                        </small>
                      </div>
                    </div>
                  ))}
                </div>
                <dl className="scope-details">
                  <div>
                    <dt>Geography</dt>
                    <dd>{plan?.geography || "All geographies"}</dd>
                  </div>
                  <div>
                    <dt>News window</dt>
                    <dd>{plan?.news_lookback_days || days} days</dd>
                  </div>
                  <div>
                    <dt>Focus</dt>
                    <dd>{plan?.focus || "Competitive landscape"}</dd>
                  </div>
                </dl>
                <p className="micro">
                  The comparison scope stays fixed for this run.
                </p>
                <div className="sidebar-actions">
                  {active ? (
                    <Button
                      variant="outline"
                      className="full-width"
                      disabled={busy}
                      onClick={() => command("cancel")}
                    >
                      Cancel run
                      {snapshot?.status === "awaiting_review"
                        ? " & edit inputs"
                        : ""}
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      className="full-width"
                      onClick={reset}
                    >
                      New comparison / retry research
                    </Button>
                  )}
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => setRetry((n) => n + 1)}
                  >
                    Refresh status / reconnect
                  </button>
                </div>
              </>
            )}
            <div className="coverage-scope">
              <span className="eyebrow">RESEARCH COVERAGE</span>
              <div className="chips">
                {[
                  "Products & brands",
                  "Positioning",
                  "Customers",
                  "Geography",
                  "Differentiators",
                  "Recent news",
                  "5 financial metrics",
                ].map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
            </div>
            {snapshot?.budget && (
              <details className="budget-details">
                <summary>Reserved run budget</summary>
                <p className="micro">
                  Reservations are estimates, not billing.
                </p>
                {Object.entries(snapshot.budget.reserved).map(([k, v]) => (
                  <p className="micro" key={k}>
                    {k.replaceAll("_", " ")}{" "}
                    <strong>
                      {v.toLocaleString()} /{" "}
                      {snapshot.budget.limits[k]?.toLocaleString() || "—"}
                    </strong>
                  </p>
                ))}
              </details>
            )}
          </div>
          <div className="sidebar-footer">
            <Icon name="info" size={14} />
            <span>Temporary session · no saved reports</span>
          </div>
        </aside>
        <main className={`canvas ${view !== "setup" ? "mobile-active" : ""}`}>
          {error && (
            <aside role="alert" className="notice error">
              {error}
              {handle && (
                <button
                  className="text-button"
                  onClick={() => {
                    setError("");
                    setRetry((n) => n + 1);
                  }}
                >
                  Retry connection
                </button>
              )}
            </aside>
          )}
          {!restored ? (
            <p role="status">Restoring local session…</p>
          ) : view === "briefing" && report ? (
            <ReportView report={report} runStatus={snapshot?.status} />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="breadcrumb">
                    Workspace <Icon name="chevron" size={12} />
                    {handle ? "Research run" : "New comparison"}
                  </div>
                  <h1>
                    {view === "setup" && handle
                      ? "Your comparison scope"
                      : handle
                        ? snapshot && terminal.has(snapshot.status)
                          ? "Research activity"
                          : "Research in motion"
                        : "A new perspective on your market"}
                  </h1>
                  <p>
                    {view === "setup" && handle
                      ? "Review the fixed scope in the sidebar. Cancel this run to change companies."
                      : handle
                        ? "Follow the evidence from company resolution to a source-backed briefing."
                        : "Start with four companies. Build a comparison you can trace back to the source."}
                  </p>
                </div>
                <span className="edition">
                  PROJECT 3A <span>/</span> MARKET INTELLIGENCE
                </span>
              </div>
              <div className="cockpit">
                <section className="card workflow-card">
                  <Progress
                    snapshot={snapshot}
                    connection={handle ? connection : "Ready to begin"}
                  />
                  {!handle && (
                    <div className="workflow-note">
                      <Icon name="info" />
                      <p>
                        First, review the resolved companies and official
                        websites. You stay in control of when research starts.
                      </p>
                    </div>
                  )}
                  {snapshot?.error && (
                    <p className="notice">
                      Research stopped: {snapshot.error.replaceAll("_", " ")}.
                      Retained evidence is available in the briefing.
                    </p>
                  )}
                </section>
                <section className="card briefing-preview">
                  {snapshot?.status === "awaiting_review" && plan ? (
                    <>
                      <div className="section-head">
                        <div>
                          <span className="eyebrow">HUMAN REVIEW</span>
                          <h2>Confirm your companies</h2>
                        </div>
                        <span className="badge amber">Approval needed</span>
                      </div>
                      <p className="muted">
                        Check identities, official websites and competitive
                        overlap before continuing.
                      </p>
                      <div className="review-list">
                        {companies.map((c, i) => (
                          <article className="identity" key={c.company_id}>
                            <span className={`company-avatar color-${i}`}>
                              {c.ticker?.slice(0, 2) ||
                                c.legal_name.slice(0, 2)}
                            </span>
                            <div>
                              <span className="eyebrow">
                                {i === 0 ? "TARGET" : `COMPETITOR ${i}`}
                              </span>
                              <h3>{c.legal_name}</h3>
                              <a
                                href={safeUrl(c.website)}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {c.website} ↗
                              </a>
                              <p className="micro">
                                {c.ticker || "No ticker"} ·{" "}
                                {c.cik
                                  ? `CIK ${c.cik}`
                                  : "SEC coverage unconfirmed"}
                              </p>
                            </div>
                          </article>
                        ))}
                      </div>
                      <p className="review-note">
                        Peers may serve different product categories and fiscal
                        periods. Cancel and edit to replace a company.
                      </p>
                      <Button
                        className="full-width"
                        disabled={busy}
                        onClick={() => command("confirm")}
                      >
                        Approve companies & start research{" "}
                        <Icon name="arrow" size={16} />
                      </Button>
                    </>
                  ) : (
                    <>
                      <div className="section-head">
                        <div>
                          <span className="eyebrow">YOUR DELIVERABLE</span>
                          <h2>
                            {report
                              ? "Your briefing is ready"
                              : "Evidence into perspective"}
                          </h2>
                        </div>
                        <Icon name="file" size={22} />
                      </div>
                      <p className="muted">
                        A structured view of your competitive landscape, with
                        evidence beside every finding.
                      </p>
                      <div className="deliverable-list">
                        {[
                          [
                            "users",
                            "Company comparison",
                            "Products, positioning, customers and geography",
                          ],
                          [
                            "chart",
                            "Financial context",
                            "Five reported metrics across three annual periods",
                          ],
                          [
                            "clock",
                            "Recent developments",
                            "Dated evidence within your news window",
                          ],
                          [
                            "link",
                            "Traceable sources",
                            "Original excerpts and official filing inputs",
                          ],
                        ].map(([icon, title, desc]) => (
                          <div key={title}>
                            <span className="feature-icon">
                              <Icon name={icon} />
                            </span>
                            <div>
                              <strong>{title}</strong>
                              <p>{desc}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                      {report ? (
                        <Button
                          className="full-width"
                          onClick={() => setView("briefing")}
                        >
                          Open briefing <Icon name="arrow" size={16} />
                        </Button>
                      ) : (
                        <div className="preview-placeholder">
                          <span className="eyebrow">
                            {handle
                              ? "RESEARCH IN PROGRESS"
                              : "AWAITING YOUR COMPARISON"}
                          </span>
                          <div className="skeleton" />
                          <div className="skeleton short" />
                          <p>
                            Findings appear when the report is compiled. Missing
                            evidence stays explicit.
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </section>
              </div>
              <p className="session-note">
                <Icon name="info" size={14} />
                Reload reconnects to your temporary run. Closing the page does
                not cancel research. Runs expire after 60 minutes of review or
                completion.
              </p>
            </>
          )}
        </main>
      </div>
      <nav className="mobile-nav" aria-label="Mobile workspace">
        {(["setup", "run", "briefing"] as const).map((key) => (
          <button
            key={key}
            disabled={key === "briefing" && !report}
            aria-current={view === key ? "page" : undefined}
            onClick={() => setView(key)}
          >
            <Icon
              name={key === "setup" ? "grid" : key === "run" ? "play" : "file"}
            />
            {key[0].toUpperCase() + key.slice(1)}
          </button>
        ))}
      </nav>
    </div>
  );
}
