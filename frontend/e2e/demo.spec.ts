import { expect, type Locator, type Page, test } from "@playwright/test";

const forbiddenVisibleText = [
  "action_id",
  "action_count",
  "tool_event_id",
  "event_id",
  "idempotency_key",
  "debug_trace",
  "execution_status",
  "feedback_status",
  "trace_id",
  "session_id",
  "node_history",
  "agent_roles",
  "api_key",
  "token",
  "secret",
  "authorization",
];

const explicitHappyPathPrompt =
  "\u4eca\u5929\u4e0b\u534814\u70b9\u5de6\u53f3\u548c\u7231\u4eba\u30015\u5c81\u7684\u5b69\u5b50\u4ece\u5f90\u6c47\u51fa\u53d1\uff0c\u5728\u5bb6\u9644\u8fd1\u73a94\u5c0f\u65f6\uff0c\u5148\u5b89\u6392\u5ba4\u5185\u4eb2\u5b50\u6d3b\u52a8\uff0c\u518d\u53bb\u5403\u4e00\u987f\u6e05\u6de1\u665a\u9910\uff0c\u5168\u7a0b\u522b\u592a\u8fdc\u3002";
const stableHappyPathPrompt =
  "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.";
const friendsGroupPrompt =
  "This afternoon I want to hang out with friends nearby for a few hours. Start with an outdoor walk and chatting, then find a casual dinner place that's good for sharing. Not too far.";
const stableClarificationReply =
  "We are leaving around 2pm this afternoon from Xuhui with my wife and 5-year-old child for about 4 hours. Keep it nearby if possible, but going a bit farther is okay if it keeps the plan relaxed. Please start with an indoor child-friendly activity and then a light dinner.";
const explicitHappyPathClarificationReply =
  "\u4eca\u5929\u4e0b\u534814\u70b9\u5de6\u53f3\u548c\u7231\u4eba\u30015\u5c81\u7684\u5b69\u5b50\u4ece\u5f90\u6c47\u51fa\u53d1\uff0c\u5728\u5bb6\u9644\u8fd1\u73a94\u5c0f\u65f6\uff0c\u5148\u5b89\u6392\u5ba4\u5185\u4eb2\u5b50\u6d3b\u52a8\uff0c\u518d\u53bb\u5403\u4e00\u987f\u6e05\u6de1\u665a\u9910\uff0c\u5168\u7a0b\u522b\u592a\u8fdc\u3002";
const vagueChinesePrompt = "\u60f3\u5468\u672b\u51fa\u53bb\u73a9\u4e00\u4e0b\u3002";
const vagueChineseClarificationReply =
  "\u4eca\u5929\u4e0b\u5348\u4e00\u4e2a\u4eba\u51fa\u95e8\u73a9\u51e0\u4e2a\u5c0f\u65f6\uff0c\u522b\u592a\u8fdc\u3002";
const liveReplanReply = "Keep it nearby, but make it a solo outing this time.";

async function fillMainComposer(page: Page, prompt: string) {
  await page.getByTestId("main-composer-input").fill(prompt);
}

async function startRun(page: Page, prompt: string) {
  await page.goto("/");
  await fillMainComposer(page, prompt);
  await page.getByTestId("start-button").click();
}

async function expectEarlyProgressFeedback(page: Page) {
  await expect
    .poll(async () => {
      if ((await page.getByTestId("progress-stepper-card").count()) > 0) {
        return "progress-card";
      }
      if ((await page.getByTestId("system-progress").count()) > 0) {
        return "spinner";
      }
      return "none";
    }, { timeout: 60_000 })
    .toMatch(/spinner|progress-card/);
}

async function waitForConversationStage(page: Page) {
  await expect
    .poll(async () => {
      if ((await page.getByTestId("replan-panel").count()) > 0) {
        const input = page.getByTestId("main-composer-input");
        if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
          return "confirmation";
        }
      }
      if ((await page.getByTestId("clarification-card").count()) > 0) {
        const input = page.getByTestId("main-composer-input");
        if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
          return "clarification";
        }
      }
      if ((await page.getByTestId("assistant-result-card").count()) > 0) {
        return "result";
      }
      return "pending";
    }, { timeout: 60_000 })
    .toMatch(/clarification|confirmation|result/);

  if ((await page.getByTestId("replan-panel").count()) > 0) {
    const input = page.getByTestId("main-composer-input");
    if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
      return "confirmation";
    }
  }
  if ((await page.getByTestId("clarification-card").count()) > 0) {
    const input = page.getByTestId("main-composer-input");
    if ((await input.count()) > 0 && (await input.isEditable().catch(() => false))) {
      return "clarification";
    }
  }
  if ((await page.getByTestId("assistant-result-card").count()) > 0) {
    return "result";
  }
  return "result";
}

async function currentVisiblePlanVersion(page: Page) {
  const versionBadge = page.locator(".thread-badge").filter({ hasText: /^v\d+$/ }).last();
  await expect(versionBadge).toBeVisible({ timeout: 60_000 });
  return (await versionBadge.innerText()).trim();
}

async function expectThreadItemOrder(first: Locator, second: Locator) {
  const [firstIndex, secondIndex] = await Promise.all([
    first.evaluate((node) => {
      const article = node.closest("article");
      return article ? Array.from(document.querySelectorAll("article")).indexOf(article) : -1;
    }),
    second.evaluate((node) => {
      const article = node.closest("article");
      return article ? Array.from(document.querySelectorAll("article")).indexOf(article) : -1;
    }),
  ]);

  expect(firstIndex).toBeGreaterThanOrEqual(0);
  expect(secondIndex).toBeGreaterThanOrEqual(0);
  expect(firstIndex).toBeLessThan(secondIndex);
}

async function expectLatestProgressStepperCollapsed(page: Page) {
  const card = page.getByTestId("progress-stepper-card").last();
  await expect(card).toBeVisible({ timeout: 60_000 });
  await expect(card.getByTestId("progress-completed-toggle")).toHaveAttribute("aria-expanded", "false");
  await expect(card.getByTestId("progress-completed-list")).toHaveCount(0);
  return card;
}

async function expandLatestCompletedSteps(page: Page) {
  const card = await expectLatestProgressStepperCollapsed(page);
  const toggle = card.getByTestId("progress-completed-toggle");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(card.getByTestId("progress-completed-list")).toBeVisible();
  return card;
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
    await page.getByTestId("main-composer-input").fill(clarificationReply);
    await page.getByTestId("start-button").click();
  }

  await expect(page.getByTestId("replan-panel")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("confirm-button")).toHaveCount(1);
  expect(await currentVisiblePlanVersion(page)).toBe(expectedVersion);
  await expectLatestProgressStepperCollapsed(page);
}

async function startPresentableDemoRun(
  page: Page,
  prompt: string = stableHappyPathPrompt,
  clarificationReply: string = stableClarificationReply,
) {
  await startRun(page, prompt);
  await continueToAwaitingConfirmation(page, "v1", clarificationReply);
}

async function expectNoForbiddenVisibleText(page: Page) {
  const bodyText = (await page.locator("body").innerText()).toLowerCase();

  for (const forbidden of forbiddenVisibleText) {
    expect(bodyText, `visible page text should not include ${forbidden}`).not.toContain(forbidden);
  }
}

async function expectExecutionTimelineCollapsed(resultCard: Locator) {
  await expect(resultCard.getByTestId("execution-timeline")).toHaveCount(0);
}

function buildProgress(stage: string, stageHistory: string[], summaryOverrides: Record<string, string> = {}) {
  const labels: Record<string, string> = {
    understanding_request: "\u6b63\u5728\u7406\u89e3\u9700\u6c42",
    planning_queries: "\u6b63\u5728\u89c4\u5212\u67e5\u8be2",
    searching_activities: "\u6b63\u5728\u67e5\u8be2\u6e38\u73a9\u5730\u70b9",
    searching_dining: "\u6b63\u5728\u67e5\u8be2\u9910\u5385",
    checking_availability: "\u6b63\u5728\u68c0\u67e5\u8425\u4e1a\u4e0e\u53ef\u7528\u6027",
    building_itinerary: "\u6b63\u5728\u7ec4\u5408\u884c\u7a0b",
    checking_route_time: "\u6b63\u5728\u8ba1\u7b97\u8def\u7ebf\u4e0e\u65f6\u95f4",
    reviewing_plan: "\u6b63\u5728\u590d\u6838\u65b9\u6848",
    ready_for_confirmation: "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
    executing_confirmed_actions: "\u5df2\u786e\u8ba4\uff0c\u6b63\u5728\u6267\u884c\u52a8\u4f5c",
  };

  return {
    schema_version: "public_demo_progress_v1",
    current_stage: stage,
    current_label: labels[stage],
    stage_history: stageHistory,
    steps: stageHistory.map((current, index) => ({
      stage: current,
      label: labels[current],
      status: index === stageHistory.length - 1 ? "current" : "completed",
      summary: summaryOverrides[current] ?? labels[current],
    })),
  };
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
    progress: buildProgress(
      "ready_for_confirmation",
      [
        "understanding_request",
        "planning_queries",
        "searching_activities",
        "searching_dining",
        "checking_availability",
        "building_itinerary",
        "checking_route_time",
        "reviewing_plan",
        "ready_for_confirmation",
      ],
      {
        searching_activities: "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8",
        searching_dining: "\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385",
        building_itinerary: "\u5df2\u751f\u6210 2 \u4e2a\u5019\u9009\u65b9\u6848",
      },
    ),
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

function buildStartRunStreamBody(summary: Record<string, unknown>) {
  return [
    `event: progress\ndata: ${JSON.stringify({
      event_index: 1,
      run_id: summary.run_id,
      progress: summary.progress,
    })}\n\n`,
    `event: summary\ndata: ${JSON.stringify({
      event_index: 2,
      summary,
    })}\n\n`,
  ].join("");
}

const mockedStartRun = buildMockAwaitingRun("run-1", "plan-1", 1, "v1", null, null);
const mockedStartRunWithTwoPlans = buildMockTwoPlanAwaitingRun();
const mockedReplannedRunV2FromPlan2 = buildMockAwaitingRun("run-2", "plan-4", 2, "v2", "run-1", "plan-2");
const mockedAmapRun = {
  ...mockedStartRun,
  run_id: "run-amap",
  read_profile: "amap",
};

test.describe("desktop web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Desktop coverage runs only once.");
  });

  test("starts a run, keeps the summary-first confirmation boundary, confirms, and shows feedback", async ({ page }) => {
    await startRun(page, stableHappyPathPrompt);

    await expect(page.locator("article.thread-row-user").getByText(stableHappyPathPrompt)).toBeVisible({ timeout: 60_000 });
    await expectEarlyProgressFeedback(page);

    await continueToAwaitingConfirmation(page, "v1");

    await expect(page.getByTestId("system-progress")).toHaveCount(0);
    await expect(page.getByText("\u63a8\u8350\u65b9\u6848\u6458\u8981", { exact: true }).last()).toBeVisible();
    await expect(page.getByTestId("confirm-button")).toBeVisible();
    await expect(page.getByTestId("run-id")).toHaveCount(0);
    await expectNoForbiddenVisibleText(page);

    const progressCard = await expandLatestCompletedSteps(page);
    await expect(progressCard.getByTestId("progress-completed-list")).toContainText("\u5df2\u627e\u5230");

    await page.getByRole("button", { name: "\u65f6\u95f4\u7ebf" }).last().click();
    await expect(page.locator(".timeline-list li").first()).toBeVisible();

    await page.getByTestId("confirm-button").click();

    const resultCard = page.getByTestId("assistant-result-card").last();
    await expect(resultCard).toBeVisible({ timeout: 60_000 });
    await expectThreadItemOrder(page.getByTestId("progress-stepper-card").last(), resultCard);
    await expectExecutionTimelineCollapsed(resultCard);
    await expectNoForbiddenVisibleText(page);

    await page.getByTestId("execution-timeline-toggle").click();
    await expect(page.getByTestId("execution-timeline")).toBeVisible();
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
  });

  test("declines a fresh run without exposing confirm action afterward", async ({ page }) => {
    await startPresentableDemoRun(page);

    await page.getByTestId("decline-button").click();

    await expect(page.getByText("\u5df2\u653e\u5f03\u5f53\u524d\u65b9\u6848")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
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
    expect(await currentVisiblePlanVersion(page)).toBe("v1");
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
    await page.getByRole("button", { name: "\u6d3b\u52a8\u4e0e\u9910\u5385" }).last().click();
    await expect(page.locator("body")).toContainText(/\u9002\u5408\u670b\u53cb\u805a\u4f1a|group_friendly/);

    await page.getByTestId("confirm-button").click();

    await expect(page.getByTestId("assistant-result-card")).toBeVisible({ timeout: 60_000 });
  });

  test("continues a vague request through the clarification flow", async ({ page }) => {
    await startRun(page, vagueChinesePrompt);

    await expectEarlyProgressFeedback(page);
    const clarificationCard = page.getByTestId("clarification-card").last();
    await expect(clarificationCard).toBeVisible({ timeout: 60_000 });

    expect(await currentVisiblePlanVersion(page)).toBe("v1");

    const progressCard = await expectLatestProgressStepperCollapsed(page);
    await expectThreadItemOrder(progressCard, clarificationCard);

    await page.getByTestId("main-composer-input").fill(vagueChineseClarificationReply);
    await page.getByTestId("start-button").click();

    await continueToAwaitingConfirmation(page, "v1", vagueChineseClarificationReply);

    await expectThreadItemOrder(page.getByTestId("progress-stepper-card").last(), page.getByTestId("replan-panel").last());
  });

  test("replans from the customer page and advances the visible version", async ({ page }) => {
    await startPresentableDemoRun(page);

    await expectThreadItemOrder(page.getByTestId("progress-stepper-card").last(), page.getByTestId("replan-panel").last());

    await page.getByTestId("main-composer-input").fill(liveReplanReply);
    await page.getByTestId("start-button").click();

    await continueToAwaitingConfirmation(page, "v2");
    await expectThreadItemOrder(page.getByTestId("progress-stepper-card").last(), page.getByTestId("replan-panel").last());
    await expectNoForbiddenVisibleText(page);
  });

  test("sends the selected second plan index when replanning from the customer page", async ({ page }) => {
    const replanBodies: Array<Record<string, unknown>> = [];

    await page.route(/\/demo\/runs\/stream$/, async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: buildStartRunStreamBody(mockedStartRunWithTwoPlans),
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

    await page.getByTestId("main-composer-input").fill("Keep the backup plan, but reduce walking.");
    await page.getByTestId("start-button").click();

    await continueToAwaitingConfirmation(page, "v2");
    expect(replanBodies[0]).toEqual({
      user_input: "Keep the backup plan, but reduce walking.",
      selected_plan_index: 1,
    });
  });

  test("blocks confirmation when the server returns a map read-only preview", async ({ page }) => {
    await page.route(/\/demo\/runs\/stream$/, async (route, request) => {
      if (request.method() !== "POST") {
        await route.fallback();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: buildStartRunStreamBody(mockedAmapRun),
      });
    });

    await page.goto("/");
    await fillMainComposer(page, stableHappyPathPrompt);
    await page.getByTestId("start-button").click();

    await expect(page.getByTestId("replan-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("amap-read-only-notice")).toBeVisible();
    await expect(page.getByTestId("amap-read-only-notice")).toContainText("地图只读预览");
    await expect(page.getByTestId("confirm-button")).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("AMap");
  });

  test("does not render forbidden internal or sensitive keys", async ({ page }) => {
    await startPresentableDemoRun(page, explicitHappyPathPrompt, explicitHappyPathClarificationReply);

    await expect(page.getByTestId("run-id")).toHaveCount(0);
    await expect(page.getByTestId("run-info-toggle")).toHaveCount(0);
    await expectNoForbiddenVisibleText(page);
  });
});

test.describe("mobile web demo", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium", "Mobile smoke runs only on the mobile project.");
  });

  test("loads the main flow without document-level horizontal overflow", async ({ page }) => {
    await startRun(page, stableHappyPathPrompt);

    const stage = await waitForConversationStage(page);
    if (stage === "confirmation") {
      await expectLatestProgressStepperCollapsed(page);
      await expect(page.getByTestId("replan-panel")).toBeVisible();
      await expect(page.getByRole("button", { name: "\u65f6\u95f4\u7ebf" }).last()).toBeVisible();
    } else {
      await expectLatestProgressStepperCollapsed(page);
      await expect(page.getByTestId("clarification-card")).toBeVisible();
      await expect(page.getByTestId("start-button")).toBeVisible();
    }

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});
