import { test, expect } from "@playwright/test";
// Refuse to create runs unless the frontend points to the offline harness.
test.beforeEach(async ({ request }) => {
  const ready = await request.get("/api/v1/ready");
  expect((await ready.json()).offline_validation).toBe(true);
});
// Requires isolated OFFLINE harness on :8001 and Next with API_ORIGIN pointing there.
async function create(page: import("@playwright/test").Page, target = "HSY") {
  await page.goto("/");
  await page.getByLabel("Target company", { exact: true }).fill(target);
  await page.getByRole("button", { name: "Review research plan" }).click();
}
async function approve(page: import("@playwright/test").Page) {
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve companies" }).click();
}
test("partial workflow, approval barrier, reload, SSE reconnect, financials, citations and mobile", async ({
  page,
}) => {
  await create(page);
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  await page.waitForTimeout(500);
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  await approve(page);
  await page
    .getByRole("button", { name: "Refresh status / reconnect" })
    .click();
  await expect(page.getByText("Partial report", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Research report")).toBeVisible();
  await expect(
    page.getByText("OFFLINE TEST fixture report. Not live research.").first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Recent developments", exact: true })
    .click();
  await expect(
    page.getByText("No accepted recent developments."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Financials", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await page
    .getByText("Detailed annual values & filing evidence", { exact: true })
    .click();
  await expect(page.locator(".financial-details tbody tr")).toHaveCount(60);
  await page.getByLabel("Financial metric").selectOption("operating_margin");
  await expect(page.locator(".financial-details tbody")).toContainText("-");
  await page
    .getByRole("button", { name: "Sources", exact: false })
    .last()
    .click();
  await page.getByLabel("Search sources", { exact: true }).fill("identity");
  await page.locator(".source-card").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page
      .getByText(
        "Synthetic identity for browser validation; not live research.",
      )
      .first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close evidence" }).click();
  const keys = await page.evaluate(() => Object.keys(sessionStorage));
  expect(keys).toEqual(["project3a.run"]);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText("Partial report", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("complete report and terminal reload", async ({ page }) => {
  await create(page, "COMPLETE");
  await approve(page);
  await expect(
    page.getByText("Complete report", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Research report")).toBeVisible();
});
test("cancel before approval, new request and failure", async ({ page }) => {
  await create(page);
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel run" }).click();
  await expect(
    page.getByRole("heading", { name: "cancelled", exact: true }),
  ).toBeVisible();
  await page.getByRole('button',{name:'Open briefing',exact:true}).click();
  await expect(page.getByText('Run cancelled. This briefing contains only evidence retained before cancellation.')).toBeVisible();
  await page
    .getByRole("button", { name: "New comparison", exact: true })
    .click();
  await page.getByLabel("Target company", { exact: true }).fill("FAIL");
  await page.getByRole("button", { name: "Review research plan" }).click();
  await expect(
    page.getByRole("heading", { name: "failed", exact: true }),
  ).toBeVisible();
});
test("expired handle and retry state", async ({ page, request }) => {
  await create(page);
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  const handle = await page.evaluate(() =>
    JSON.parse(sessionStorage.getItem("project3a.run")!),
  );
  await request.post(`http://127.0.0.1:8001/__test/expire/${handle.run_id}`);
  await page.reload();
  await expect(page.locator("aside[role=alert]")).toContainText("expired");
  await page
    .getByRole("button", { name: "New comparison", exact: true })
    .click();
  await expect(
    page.getByLabel("Target company", { exact: true }),
  ).toBeVisible();
});
test("network failure reconnects with a replay cursor; cancellation during research", async ({
  page,
}) => {
  const cursors: string[] = [];
  let cut = false;
  await page.route("**/events", async (route) => {
    cursors.push(route.request().headers()["last-event-id"]);
    if (cursors.length === 2) {
      cut = true;
      await route.abort();
    } else await route.continue();
  });
  await create(page);
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Refresh status / reconnect" })
    .click();
  await expect.poll(() => cut).toBe(true);
  await expect.poll(() => cursors.length).toBeGreaterThan(2);
  expect(Number(cursors[2])).toBeGreaterThan(0);
  await approve(page);
  await page.getByRole("button", { name: "Cancel run", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "cancelled", exact: true }),
  ).toBeVisible();
});
test("unknown run, capacity error, and recovery from unavailable API", async ({
  page,
  request,
}) => {
  const active = await request.post("http://127.0.0.1:8001/api/v1/runs", {
    data: { target: "HSY", competitors: ["MDLZ", "KHC", "GIS"] },
  });
  const h = await active.json();
  await create(page);
  await expect(page.locator("aside[role=alert]")).toContainText("active run");
  await request.post(`http://127.0.0.1:8001/api/v1/runs/${h.run_id}/cancel`, {
    headers: { "X-Run-Token": h.run_token },
  });
  await page.evaluate(() =>
    sessionStorage.setItem(
      "project3a.run",
      JSON.stringify({ run_id: "unknown", run_token: "unknown" }),
    ),
  );
  await page.reload();
  await expect(page.locator("aside[role=alert]")).toContainText("unavailable");
  await page
    .getByRole("button", { name: "New comparison", exact: true })
    .click();
  await page.route("**/api/v1/ready", (route) =>
    route.fulfill({ status: 502, json: { detail: "offline" } }),
  );
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Review research plan" }),
  ).toBeDisabled();
  await page.unroute("**/api/v1/ready");
  await page.getByRole("button", { name: "Check again" }).click();
  await expect(
    page.getByRole("button", { name: "Review research plan" }),
  ).toBeEnabled();
});

test("redesigned comparison, evidence drawer, financial inputs, real company events and mobile navigation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Review research plan" }),
  ).toBeEnabled();
  await page.screenshot({
    path: "/tmp/project3a-redesign-setup.png",
    fullPage: false,
    caret: "initial",
  });
  await page.getByRole("button", { name: "Review research plan" }).click();
  await expect(
    page.getByRole("heading", { name: "awaiting review" }),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/project3a-redesign-review.png",
    fullPage: false,
    caret: "initial",
  });
  await approve(page);
  await expect(page.getByLabel("Research report")).toBeVisible();
  await expect(page.getByText("23 / 24")).toBeVisible();
  await page.screenshot({
    path: "/tmp/project3a-redesign-overview.png",
    fullPage: false,
    caret: "initial",
  });
  await page.getByRole("button", { name: "Comparison", exact: true }).click();
  await expect(page.locator(".comparison-table tbody tr")).toHaveCount(6);
  await expect(page.locator(".comparison-table thead th")).toHaveCount(5);
  const citation = page
    .locator(".comparison-table")
    .getByRole("button", { name: /View source/ })
    .first();
  await citation.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(citation).toBeFocused();
  await page.getByRole("button", { name: "Financials", exact: true }).click();
  await page.locator(".latest-table .metric-button").first().click();
  await expect(page.getByRole("dialog")).toContainText(
    "Official filing inputs",
  );
  await expect(page.getByRole("dialog")).toContainText("11692576000");
  await page.getByRole("button", { name: "Close evidence" }).click();
  await page.screenshot({
    path: "/tmp/project3a-redesign-financials.png",
    fullPage: false,
    caret: "initial",
  });
  await page
    .getByRole("button", { name: "Sources", exact: false })
    .last()
    .click();
  await page
    .getByLabel("Search sources", { exact: true })
    .fill("no such source");
  await expect(page.getByText("No sources match these filters.")).toBeVisible();
  await page
    .getByRole("navigation", { name: "Workspace", exact: true })
    .getByRole("button", { name: "Run", exact: true })
    .click();
  await expect(page.getByLabel("Company progress")).toBeVisible();
  await expect(page.getByLabel("Research activity")).toContainText(
    "Partial evidence",
  );
  await expect(page.getByLabel("Company progress")).toContainText("1 source");
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("navigation", { name: "Mobile workspace" })
    .getByRole("button", { name: "Setup" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Comparison scope" }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Mobile workspace" })
    .getByRole("button", { name: "Briefing" })
    .click();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: "/tmp/project3a-redesign-mobile.png",
    fullPage: false,
    caret: "initial",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
