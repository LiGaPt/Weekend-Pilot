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

const stableHappyPathPrompt =
  "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.";
const stableClarificationReply =
  "We are going out this afternoon with my wife and 5-year-old child for a few hours. Keep it nearby if possible, but going a bit farther is okay if it keeps the plan relaxed and the dinner light.";

async function startDemoRun(page: Page, prompt?: string) {
  await page.goto("/");
  await page.getByRole("textbox").fill(prompt ?? stableHappyPathPrompt);
  await page.getByTestId("start-button").click();
  await expect(page.getByTestId("run-status")).toHaveText("等待确认", { timeout: 60_000 });
  await expect(page.getByTestId("action-count")).toHaveText("0");
}

async function continueToAwaitingConfirmation(page: Page, expectedVersion: string) {
  await expect(page.getByTestId("plan-version")).toHaveText(expectedVersion, { timeout: 60_000 });
  await expect
    .poll(async () => (await page.getByTestId("run-status").innerText()).trim(), { timeout: 60_000 })
    .toMatch(/等待确认|等待补充信息/);

  if ((await page.getByTestId("run-status").innerText()).trim() === "等待补充信息") {
    await expect(page.getByTestId("plan-version")).toHaveText(expectedVersion);
    await expect(page.getByTestId("clarification-panel")).toBeVisible();
    await page.getByTestId("clarification-reply-input").fill(stableClarificationReply);
    await page.getByTestId("clarification-submit-button").click();
  }

  await expect(page.getByTestId("run-status")).toHaveText("等待确认", { timeout: 60_000 });
  await expect(page.getByTestId("plan-version")).toHaveText(expectedVersion);
  await expect(page.getByTestId("action-count")).toHaveText("0");
}

async function startPresentableDemoRun(page: Page, prompt?: string) {
  await page.goto("/");
  await page.getByRole("textbox").fill(prompt ?? stableHappyPathPrompt);
  await page.getByTestId("start-button").click();
  await continueToAwaitingConfirmation(page, "v1");
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

function buildMockPlan(planId: string, selected: boolean) {
  return {
    plan_id: planId,
    status: "reviewed",
    selected,
    title: "Mock family afternoon plan",
    summary: "Start with an indoor activity, then wrap up with a lighter dinner.",
    activity: {
      name: "Family Science Center",
      category: "activity",
      address: "100 Mock Science Road",
      tags: ["child_friendly", "indoor"],
    },
    dining: {
      name: "Light Table",
      category: "dining",
      address: "8 Mock Dining Street",
      tags: ["lighter_options"],
    },
    timeline: [
      {
        sequence: 1,
        title: "Indoor activity",
        start_label: "14:00",
        end_label: "16:00",
        duration_minutes: 120,
      },
    ],
    route: {
      mode: "driving",
      distance_meters: 3200,
      duration_minutes: 18,
      summary: "A short drive keeps the afternoon easy.",
    },
    feasibility: {
      is_feasible: true,
      reasons: ["Fits the requested afternoon window."],
      warnings: [],
      total_duration_minutes: 270,
      route_duration_minutes: 18,
      queue_wait_minutes: 5,
    },
    proposed_actions: [],
    action_manifest: {
      source: "proposed_actions",
      action_count: 0,
      actions: [],
    },
    confirmation: { status: "pending", action_count: 0 },
  };
}

function buildMockAwaitingRun(
  runId: string,
  planId: string,
  versionNumber: number,
  versionLabel: string,
  sourceRunId: string | null,
  sourceSelectedPlanId: string | null,
) {
  return {
    run_id: runId,
    status: "awaiting_confirmation",
    read_profile: "mock_world",
    selected_plan_id: planId,
    plan_version: {
      version_number: versionNumber,
      version_label: versionLabel,
      source_run_id: sourceRunId,
      source_selected_plan_id: sourceSelectedPlanId,
    },
    plans: [buildMockPlan(planId, true)],
    action_count: 0,
    execution_status: null,
    feedback_status: null,
    error: null,
    clarification: null,
  };
}

const mockedStartRun = buildMockAwaitingRun("run-1", "plan-1", 1, "v1", null, null);
const mockedReplannedRunV2 = buildMockAwaitingRun("run-2", "plan-2", 2, "v2", "run-1", "plan-1");
const mockedReplannedRunV3 = buildMockAwaitingRun("run-3", "plan-3", 3, "v3", "run-2", "plan-2");

test.describe("desktop web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Desktop coverage runs only once.");
  });

  test("starts a run, preserves confirmation boundary, confirms, and shows feedback", async ({ page }) => {
    await startPresentableDemoRun(page);

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
    await startPresentableDemoRun(page);

    await page.getByTestId("decline-button").click();

    await expect(page.getByTestId("run-status")).toHaveText("已放弃", { timeout: 60_000 });
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("refreshes status without losing the current run", async ({ page }) => {
    await startPresentableDemoRun(page);
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

  test("replans from the customer page and advances the visible version", async ({ page }) => {
    const startBodies: Array<Record<string, unknown>> = [];
    const replanBodies: Array<Record<string, unknown>> = [];
    let replanCallCount = 0;

    await page.route("**/demo/runs", async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      startBodies.push((request.postDataJSON() as Record<string, unknown>) ?? {});
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockedStartRun),
      });
    });

    await page.route(/\/demo\/runs\/[^/]+\/replan$/, async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      replanBodies.push((request.postDataJSON() as Record<string, unknown>) ?? {});
      const responseBody = replanCallCount === 0 ? mockedReplannedRunV2 : mockedReplannedRunV3;
      replanCallCount += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(responseBody),
      });
    });

    await startPresentableDemoRun(page);
    expect(startBodies).toHaveLength(1);
    expect(startBodies[0]?.selected_plan_index).toBe(0);
    expect(startBodies[0]?.read_profile).toBe("mock_world");

    await expect(page.getByTestId("plan-version")).toHaveText("v1");
    await expect(page.getByTestId("replan-panel")).toBeVisible();

    const sourceRunId = (await page.getByTestId("run-id").innerText()).trim();

    await page
      .getByTestId("replan-reply-input")
      .fill("Keep it nearby, but make it indoor this time.");
    await page.getByTestId("replan-submit-button").click();
    await continueToAwaitingConfirmation(page, "v2");
    expect(replanBodies[0]).toEqual({
      user_input: "Keep it nearby, but make it indoor this time.",
      selected_plan_index: 0,
    });

    await expect(page.getByTestId("run-status")).toHaveText("等待确认", { timeout: 60_000 });
    await expect(page.getByTestId("plan-version")).toHaveText("v2");
    await expect(page.getByTestId("confirm-button")).toBeVisible();

    const replannedRunId = (await page.getByTestId("run-id").innerText()).trim();
    expect(replannedRunId).not.toBe(sourceRunId);

    await page.getByTestId("replan-reply-input").fill("Keep it nearby again, but reduce walking even more.");
    await page.getByTestId("replan-submit-button").click();
    await continueToAwaitingConfirmation(page, "v3");
    expect(replanBodies[1]).toEqual({
      user_input: "Keep it nearby again, but reduce walking even more.",
      selected_plan_index: 0,
    });

    await expect(page.getByTestId("run-status")).toHaveText("等待确认", { timeout: 60_000 });
    await expect(page.getByTestId("plan-version")).toHaveText("v3");
    await expect(page.getByTestId("run-id")).not.toHaveText(replannedRunId);
  });

  test("does not render forbidden internal or sensitive keys", async ({ page }) => {
    await startPresentableDemoRun(page);
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
    await page.getByRole("textbox").fill(stableHappyPathPrompt);
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
