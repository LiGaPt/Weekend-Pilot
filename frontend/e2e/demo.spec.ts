import { expect, type Page, test } from "@playwright/test";

const forbiddenVisibleText = [
  "action_id",
  "tool_event_id",
  "event_id",
  "idempotency_key",
  "debug_trace",
  "api_key",
  "token",
  "secret",
  "authorization",
];

async function startDemoRun(page: Page) {
  await page.goto("/");
  await page.getByTestId("start-button").click();
  await expect(page.getByTestId("run-status")).toHaveText("awaiting_confirmation", { timeout: 60_000 });
  await expect(page.getByTestId("action-count")).toHaveText("0");
}

async function expectNoForbiddenVisibleText(page: Page) {
  const bodyText = (await page.locator("body").innerText()).toLowerCase();

  for (const forbidden of forbiddenVisibleText) {
    expect(bodyText, `visible page text should not include ${forbidden}`).not.toContain(forbidden);
  }
}

async function visibleActionCount(page: Page) {
  const text = (await page.getByTestId("action-count").innerText()).trim();
  const count = Number.parseInt(text, 10);
  expect(Number.isNaN(count), `action count should be numeric, got ${text}`).toBe(false);
  return count;
}

test.describe("desktop web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Desktop coverage runs only once.");
  });

  test("starts a run, preserves confirmation boundary, confirms, and shows feedback", async ({ page }) => {
    await startDemoRun(page);

    await expect(page.getByText("Confirmation boundary")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Timeline" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Action preview" })).toBeVisible();
    await expect(page.getByTestId("confirm-button")).toBeVisible();
    expect(await visibleActionCount(page)).toBe(0);

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("completed", { timeout: 60_000 });
    await expect(page.getByText("Execution and feedback")).toBeVisible();
    await expect(page.getByText("Completed actions")).toBeVisible();
    expect(await visibleActionCount(page)).toBeGreaterThan(0);
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("declines a fresh run without exposing confirm action afterward", async ({ page }) => {
    await startDemoRun(page);

    await page.getByTestId("decline-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("declined", { timeout: 60_000 });
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("refreshes status without losing the current run", async ({ page }) => {
    await startDemoRun(page);
    const runId = (await page.getByTestId("run-id").innerText()).trim();

    await page.getByTestId("refresh-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("awaiting_confirmation", { timeout: 60_000 });
    await expect(page.getByTestId("run-id")).toHaveText(runId);
  });

  test("does not render forbidden internal or sensitive keys", async ({ page }) => {
    await startDemoRun(page);
    await expectNoForbiddenVisibleText(page);

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("completed", { timeout: 60_000 });
    await expectNoForbiddenVisibleText(page);
  });
});

test.describe("mobile web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium", "Mobile smoke runs only on the mobile project.");
  });

  test("loads the main flow without document-level horizontal overflow", async ({ page }) => {
    await startDemoRun(page);

    await expect(page.getByTestId("confirm-button")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Timeline" })).toBeVisible();

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});
