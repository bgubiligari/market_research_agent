import { test } from "node:test";
import assert from "node:assert/strict";
import { decimal, safeUrl, SSEParser } from "../lib/client";
test("Decimal wire values preserve valid negatives and reject missing or malformed values", () => {
  assert.equal(decimal("0"), 0);
  assert.equal(decimal("-52.125"), -52.125);
  assert.equal(decimal("11692576000"), 11692576000);
  for (const v of [null, "", " ", "NaN", "Infinity", "12USD"])
    assert.equal(decimal(v), null);
});
test("source links allow only HTTP protocols", () => {
  assert.equal(safeUrl("javascript:alert(1)"), undefined);
  assert.equal(safeUrl("https://www.sec.gov/"), "https://www.sec.gov/");
});
test("SSE parser survives byte framing boundaries, comments, CRLF and replay IDs", () => {
  const parser = new SSEParser();
  assert.deepEqual(
    parser.feed(": heartbeat\r\n\r\nid: 12\r\nevent: status\r\nda"),
    [],
  );
  const frames = parser.feed(
    'ta: {"status":"awaiting_review"}\r\n\r\nid: 13\ndata: {"status":"partial"}\n\n',
  );
  assert.deepEqual(
    frames.map((f) => [f.id, f.data.status]),
    [
      [12, "awaiting_review"],
      [13, "partial"],
    ],
  );
});
import { chartData } from "../lib/financials";
import type { Metric } from "../lib/contracts";
test("charts separate currencies, preserve negative values and leave unsupported periods empty", () => {
  const row = (
    company_id: string,
    year: number,
    value: string | null,
    status = "available",
    unit = "USD",
  ): Metric => ({
    company_id,
    metric: "revenue",
    value,
    status,
    unit,
    period: { start: `${year}-01-01`, end: `${year}-12-31`, fiscal_year: year },
    input_fact_ids: [],
    reason: null,
    breakdown: null,
  });
  const metrics = [
    row("a", 2024, "120"),
    row("a", 2025, null, "unavailable"),
    row("b", 2025, "25", "available", "EUR"),
    row("c", 2025, "-15"),
  ];
  assert.deepEqual(chartData(metrics, ["a", "b", "c"], "revenue", "USD"), [
    { year: 2024, a: 120, b: null, c: null },
    { year: 2025, a: null, b: null, c: -15 },
  ]);
  assert.deepEqual(chartData(metrics, ["a", "b", "c"], "revenue", "EUR"), [
    { year: 2025, a: null, b: 25, c: null },
  ]);
  assert.deepEqual(
    chartData(
      [row("a", 2025, null, "not_meaningful")],
      ["a"],
      "revenue",
      "USD",
    ),
    [{ year: 2025, a: null }],
  );
});
import { metricValue } from "../lib/presentation";
test("financial display preserves zero and negative percentages, marks unavailable values explicitly", () => {
  const metric = {
    metric: "operating_margin",
    value: "0",
    unit: "percent",
    status: "available",
  } as Metric;
  assert.equal(metricValue(metric), "0%");
  assert.equal(metricValue({ ...metric, value: "-18.72" }), "-18.72%");
  assert.equal(
    metricValue({ ...metric, value: null, status: "not_meaningful" }),
    "Not meaningful",
  );
  assert.equal(metricValue(undefined), "Unavailable");
  assert.equal(
    metricValue({ ...metric, value: "11692576000", unit: "USD" }, true),
    "USD 11.69bn",
  );
});
