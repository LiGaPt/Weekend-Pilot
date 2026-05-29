import { expect, type Locator, type Page, test } from "@playwright/test";

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
  "今天下午14点左右和爱人、5岁的孩子从徐汇出发，在家附近玩 4 小时，先安排室内亲子活动，再去吃一顿清淡晚餐，全程别太远。";

const stableHappyPathPrompt =
  "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.";
const friendsGroupPrompt =
  "This afternoon I want to hang out with friends nearby for a few hours. Start with an outdoor walk and chatting, then find a casual dinner place that's good for sharing. Not too far.";
const stableClarificationReply =
  "We are leaving around 2pm this afternoon from Xuhui with my wife and 5-year-old child for about 4 hours. Keep it nearby if possible, but going a bit farther is okay if it keeps the plan relaxed. Please start with an indoor child-friendly activity and then a light dinner.";
const explicitHappyPathClarificationReply =
  "今天下午14点左右和爱人、5岁的孩子从徐汇出发，在家附近玩 4 小时，先安排室内亲子活动，再去吃一顿清淡晚餐，全程别太远。";

async function fillMainComposer(page: Page, prompt: string) {
  await page.getByRole("textbox").first().fill(prompt);
}

async function waitForConversationStage(page: Page) {
  await expect
    .poll(async () => {
      if ((await page.getByTestId("clarification-card").count()) > 0) {
        const input = page.getByTestId("clarification-reply-input");
        if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
          return "clarification";
        }
      }
      if ((await page.getByTestId("replan-panel").count()) > 0) {
        const input = page.getByTestId("replan-reply-input");
        if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
          return "confirmation";
        }
      }
      if ((await page.getByTestId("assistant-result-card").count()) > 0) {
        return "result";
      }
      return "pending";
    }, { timeout: 60_000 })
    .toMatch(/clarification|confirmation|result/);

  if ((await page.getByTestId("clarification-card").count()) > 0) {
    const input = page.getByTestId("clarification-reply-input");
    if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
        return "clarification";
      }
  }
  if ((await page.getByTestId("replan-panel").count()) > 0) {
    const input = page.getByTestId("replan-reply-input");
    if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
        return "confirmation";
      }
  }
  if ((await page.getByTestId("assistant-result-card").count()) > 0) {
    return "result";
  }
  return "result";
}

async function openLatestRunInfo(page: Page) {
  const toggle = page.getByTestId("run-info-toggle").last();
  await expect(toggle).toBeVisible({ timeout: 60_000 });
  if ((await toggle.getAttribute("aria-expanded")) !== "true") {
    await toggle.click();
  }
}

async function currentRunInfoText(page: Page, testId: string) {
  await openLatestRunInfo(page);
  const text = (await page.getByTestId(testId).last().innerText()).trim();
  const toggle = page.getByTestId("run-info-toggle").last();
  if ((await toggle.getAttribute("aria-expanded")) === "true") {
    await toggle.click();
  }
  return text;
}

async function continueToAwaitingConfirmation(
  page: Page,
  expectedVersion: string,
  clarificationReply: string = stableClarificationReply,
) {
  for (let clarificationAttempt = 0; clarificationAttempt < 2; clarificationAttempt += 1) {
    const stage = await waitForConversationStage(page);
    if (stage === "confirmation") {
      break;
    }

    expect(stage).toBe("clarification");
    await page.getByTestId("clarification-reply-input").fill(clarificationReply);
    await page.getByTestId("clarification-submit-button").click();
  }

  await expect(page.getByTestId("replan-panel")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("confirm-button")).toHaveCount(1);
  expect(await currentRunInfoText(page, "plan-version")).toBe(expectedVersion);
}

async function startPresentableDemoRun(
  page: Page,
  prompt?: string,
  clarificationReply: string = stableClarificationReply,
) {
  await page.goto("/");
  await fillMainComposer(page, prompt ?? stableHappyPathPrompt);
  await page.getByTestId("start-button").click();
  await continueToAwaitingConfirmation(page, "v1", clarificationReply);
}

async function expectNoForbiddenVisibleText(page: Page) {
  const bodyText = (await page.locator("body").innerText()).toLowerCase();

  for (const forbidden of forbiddenVisibleText) {
    expect(bodyText, `visible page text should not include ${forbidden}`).not.toContain(forbidden);
  }
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

function buildMockTwoPlanAwaitingRun() {
  return {
    ...mockedStartRun,
    plans: [
      buildMockPlan("plan-1", true),
      {
        ...buildMockPlan("plan-2", false),
        title: "Mock backup plan",
        summary: "A second mock plan used to verify selected-plan follow-up requests.",
      },
    ],
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
const mockedStartRunWithTwoPlans = buildMockTwoPlanAwaitingRun();
const mockedReplannedRunV2FromPlan2 = buildMockAwaitingRun("run-2", "plan-4", 2, "v2", "run-1", "plan-2");
const mockedAmapRun = {
  ...mockedStartRun,
  run_id: "run-amap",
  read_profile: "amap",
};
const mockedCompletedRun = {
  ...mockedStartRun,
  status: "completed",
  action_count: 1,
  execution_status: "succeeded",
  feedback_status: "written",
  plans: [
    {
      ...mockedStartRun.plans[0],
      status: "executed",
      action_manifest: {
        source: "confirmed_actions",
        action_count: 1,
        actions: [
          {
            action_ref: "draft_1_action_1",
            execution_order: 1,
            action_type: "reserve_restaurant",
            target_id: "green-table",
            payload_preview: { party_size: 3 },
            reason: "Confirm to lock dinner seating.",
          },
        ],
      },
      confirmation: {
        status: "confirmed",
        action_count: 1,
      },
      execution: {
        status: "succeeded",
        started_at: "2026-05-26T14:00:00+08:00",
        finished_at: "2026-05-26T14:02:00+08:00",
        succeeded_count: 1,
        failed_count: 0,
        action_results: [
          {
            action_ref: "draft_1_action_1",
            execution_order: 1,
            tool_name: "reserve_restaurant",
            target_id: "green-table",
            status: "succeeded",
          },
        ],
      },
      feedback: {
        status: "written",
        headline: "Plan completed",
        message: "The confirmed reservation completed successfully.",
        completed_actions: [{ action_type: "reserve_restaurant", status: "succeeded" }],
        failed_actions: [],
        next_steps: ["Leave a little before 2pm."],
      },
    },
  ],
};

async function expectTimelineDisclosure(locator: Locator) {
  await expect(locator).toHaveCount(0);
}

test.describe("desktop web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Desktop coverage runs only once.");
  });

  test("starts a run, keeps the summary-first confirmation boundary, confirms, and shows feedback", async ({ page }) => {
    await startPresentableDemoRun(page);

    await expect(page.getByText("推荐方案摘要", { exact: true }).last()).toBeVisible();
    await expect(page.getByTestId("confirm-button")).toBeVisible();
    await expect(page.getByTestId("run-id")).toHaveCount(0);
    await expectTimelineDisclosure(page.locator(".timeline-list li"));

    await page.getByRole("button", { name: "时间线" }).last().click();
    await expect(page.locator(".timeline-list li").first()).toBeVisible();

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("assistant-result-card")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('[data-testid="assistant-result-card"] h2')).toBeVisible();
    await expectTimelineDisclosure(page.getByTestId("execution-timeline"));
    await page.getByTestId("execution-timeline-toggle").click();
    await expect(page.getByTestId("execution-timeline")).toBeVisible();
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("declines a fresh run without exposing confirm action afterward", async ({ page }) => {
    await startPresentableDemoRun(page);

    await page.getByTestId("decline-button").click();

    await expect(page.getByText("已放弃当前方案")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("refreshes status without duplicating the current run card", async ({ page }) => {
    await startPresentableDemoRun(page);
    const runId = await currentRunInfoText(page, "run-id");

    await openLatestRunInfo(page);
    await page.getByTestId("refresh-button").last().click();

    await expect(page.getByTestId("replan-panel")).toBeVisible({ timeout: 60_000 });
    expect(await currentRunInfoText(page, "run-id")).toBe(runId);
  });

  test("reaches a confirmable plan from the Chinese reviewer prompt", async ({ page }) => {
    const clarificationBodies: Array<Record<string, unknown>> = [];

    await page.route(/\/demo\/runs\/[^/]+\/clarify$/, async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      clarificationBodies.push((request.postDataJSON() as Record<string, unknown>) ?? {});
      await route.fallback();
    });

    await startPresentableDemoRun(page, explicitHappyPathPrompt, explicitHappyPathClarificationReply);

    await expect(page.getByTestId("confirm-button")).toBeVisible();
    expect(await currentRunInfoText(page, "plan-version")).toBe("v1");
    await expect(page.getByTestId("amap-read-only-notice")).toHaveCount(0);

    if (clarificationBodies.length > 0) {
      for (const body of clarificationBodies) {
        expect(body).toEqual({
          user_input: explicitHappyPathClarificationReply,
          selected_plan_index: 0,
        });
      }
    }
  });

  test("friends-group sample reaches the confirm boundary and completion", async ({ page }) => {
    await startPresentableDemoRun(page, friendsGroupPrompt, friendsGroupPrompt);

    await expect(page.getByTestId("confirm-button")).toBeVisible();
    await page.getByRole("button", { name: "活动与餐厅" }).last().click();
    await expect(page.locator("body")).toContainText(/适合朋友聚会|group_friendly/);

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("assistant-result-card")).toBeVisible({ timeout: 60_000 });
  });

  test("continues a vague request through the clarification flow", async ({ page }) => {
    await page.goto("/");
    await fillMainComposer(page, "想周末出去玩一下。");
    await page.getByTestId("start-button").click();

    await expect(page.getByTestId("clarification-card")).toBeVisible({ timeout: 60_000 });
    expect(await currentRunInfoText(page, "plan-version")).toBe("v1");
    const sourceRunId = await currentRunInfoText(page, "run-id");

    await page.getByTestId("clarification-reply-input").fill("今天下午一个人出门玩几个小时，别太远。");
    await page.getByTestId("clarification-submit-button").click();

    await continueToAwaitingConfirmation(page, "v1", "今天下午一个人出门玩几个小时，别太远。");
    expect(await currentRunInfoText(page, "run-id")).not.toBe(sourceRunId);
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

    const sourceRunId = await currentRunInfoText(page, "run-id");

    await page.getByTestId("replan-reply-input").fill("Keep it nearby, but make it indoor this time.");
    await page.getByTestId("replan-submit-button").click();
    await continueToAwaitingConfirmation(page, "v2");
    expect(replanBodies[0]).toEqual({
      user_input: "Keep it nearby, but make it indoor this time.",
      selected_plan_index: 0,
    });

    const replannedRunId = await currentRunInfoText(page, "run-id");
    expect(replannedRunId).not.toBe(sourceRunId);

    await page.getByTestId("replan-reply-input").fill("Keep it nearby again, but reduce walking even more.");
    await page.getByTestId("replan-submit-button").click();
    await continueToAwaitingConfirmation(page, "v3");
    expect(replanBodies[1]).toEqual({
      user_input: "Keep it nearby again, but reduce walking even more.",
      selected_plan_index: 0,
    });

    expect(await currentRunInfoText(page, "run-id")).not.toBe(replannedRunId);
  });

  test("sends the selected second plan index when replanning from the customer page", async ({ page }) => {
    const replanBodies: Array<Record<string, unknown>> = [];

    await page.route("**/demo/runs", async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockedStartRunWithTwoPlans),
      });
    });

    await page.route(/\/demo\/runs\/[^/]+\/replan$/, async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      replanBodies.push((request.postDataJSON() as Record<string, unknown>) ?? {});
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockedReplannedRunV2FromPlan2),
      });
    });

    await startPresentableDemoRun(page);

    const planTabs = page.getByRole("tab");
    await expect(planTabs).toHaveCount(2);
    await planTabs.nth(1).click();
    await expect(planTabs.nth(0)).toHaveAttribute("aria-selected", "false");
    await expect(planTabs.nth(1)).toHaveAttribute("aria-selected", "true");

    await page.getByTestId("replan-reply-input").fill("Keep the backup plan, but reduce walking.");
    await page.getByTestId("replan-submit-button").click();

    await continueToAwaitingConfirmation(page, "v2");
    expect(replanBodies[0]).toEqual({
      user_input: "Keep the backup plan, but reduce walking.",
      selected_plan_index: 1,
    });
  });

  test("keeps AMap preview behind advanced options and blocks confirmation", async ({ page }) => {
    await page.route("**/demo/runs", async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockedAmapRun),
      });
    });

    await page.goto("/");
    await fillMainComposer(page, stableHappyPathPrompt);
    await page.getByTestId("advanced-options-toggle").click();
    await page.getByTestId("read-profile-select").selectOption("amap");
    await page.getByTestId("start-button").click();

    await expect(page.getByTestId("replan-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("amap-read-only-notice")).toBeVisible();
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
    expect(await currentRunInfoText(page, "active-read-profile")).toBe("AMap 只读预览");
  });

  test("does not render forbidden internal or sensitive keys", async ({ page }) => {
    await page.route("**/demo/runs", async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockedStartRun),
      });
    });

    await page.route(/\/demo\/runs\/[^/]+\/confirm$/, async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockedCompletedRun),
      });
    });

    await startPresentableDemoRun(page, explicitHappyPathPrompt, explicitHappyPathClarificationReply);
    await expectNoForbiddenVisibleText(page);

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("assistant-result-card")).toBeVisible({ timeout: 60_000 });
    await expectNoForbiddenVisibleText(page);
  });
});

test.describe("mobile web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium", "Mobile smoke runs only on the mobile project.");
  });

  test("loads the main flow without document-level horizontal overflow", async ({ page }) => {
    await page.goto("/");
    await fillMainComposer(page, stableHappyPathPrompt);
    await page.getByTestId("start-button").click();

    const stage = await waitForConversationStage(page);
    if (stage === "confirmation") {
      await expect(page.getByTestId("replan-panel")).toBeVisible();
      await expect(page.getByRole("button", { name: "时间线" }).last()).toBeVisible();
    } else {
      await expect(page.getByTestId("clarification-card")).toBeVisible();
      await expect(page.getByTestId("clarification-submit-button")).toBeVisible();
    }

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});
