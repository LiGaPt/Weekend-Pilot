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

const explicitHappyPathPrompt =
  "今天下午14点左右和爱人、5岁的孩子从徐汇出发，在家附近玩4小时，先安排室内亲子活动，再去吃一顿清淡晚餐，全程别太远。";

async function startDemoRun(page: Page, prompt?: string) {
  await page.goto("/");
  if (prompt) {
    await page.getByRole("textbox").fill(prompt);
  }
  await page.getByTestId("start-button").click();
  await expect(page.getByTestId("run-status")).toHaveText("等待确认", { timeout: 60_000 });
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

    await expect(page.getByText("确认边界")).toBeVisible();
    await expect(page.getByRole("heading", { name: "行程时间线" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "执行动作预览" })).toBeVisible();
    await expect(page.getByTestId("confirm-button")).toBeVisible();
    expect(await visibleActionCount(page)).toBe(0);

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("已完成", { timeout: 60_000 });
    await expect(page.getByText("执行与反馈")).toBeVisible();
    await expect(page.getByText("已完成动作")).toBeVisible();
    expect(await visibleActionCount(page)).toBeGreaterThan(0);
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("declines a fresh run without exposing confirm action afterward", async ({ page }) => {
    await startDemoRun(page);

    await page.getByTestId("decline-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("已放弃", { timeout: 60_000 });
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("refreshes status without losing the current run", async ({ page }) => {
    await startDemoRun(page);
    const runId = (await page.getByTestId("run-id").innerText()).trim();

    await page.getByTestId("refresh-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("等待确认", { timeout: 60_000 });
    await expect(page.getByTestId("run-id")).toHaveText(runId);
  });

  test("continues a vague request through the clarification flow", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("textbox").fill("想周末出去玩一下。");
    await page.getByTestId("start-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("等待补充信息", { timeout: 60_000 });
    await expect(page.getByTestId("plan-version")).toHaveText("v1");
    await expect(page.getByTestId("action-count")).toHaveText("0");
    await expect(page.getByTestId("clarification-panel")).toBeVisible();

    const sourceRunId = (await page.getByTestId("run-id").innerText()).trim();

    await page
      .getByTestId("clarification-reply-input")
      .fill("今天下午一个人出门玩几个小时，别太远。");
    await page.getByTestId("clarification-submit-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("等待确认", { timeout: 60_000 });
    await expect(page.getByTestId("plan-version")).toHaveText("v1");
    await expect(page.getByTestId("confirm-button")).toBeVisible();

    const nextRunId = (await page.getByTestId("run-id").innerText()).trim();
    expect(nextRunId).not.toBe(sourceRunId);
  });

  test("does not render forbidden internal or sensitive keys", async ({ page }) => {
    await startDemoRun(page);
    await expectNoForbiddenVisibleText(page);

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("已完成", { timeout: 60_000 });
    await expectNoForbiddenVisibleText(page);
  });
});

test.describe("mobile web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium", "Mobile smoke runs only on the mobile project.");
  });

  test("loads the main flow without document-level horizontal overflow", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("textbox").fill(explicitHappyPathPrompt);
    await page.getByTestId("start-button").click();

    await expect
      .poll(async () => (await page.getByTestId("run-status").innerText()).trim(), { timeout: 60_000 })
      .toMatch(/等待确认|等待补充信息/);

    const status = (await page.getByTestId("run-status").innerText()).trim();
    if (status === "等待确认") {
      await expect(page.getByTestId("confirm-button")).toBeVisible();
      await expect(page.getByRole("heading", { name: "行程时间线" })).toBeVisible();
    } else {
      await expect(page.getByTestId("clarification-panel")).toBeVisible();
      await expect(page.getByTestId("clarification-submit-button")).toBeVisible();
    }

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});
