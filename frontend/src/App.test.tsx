import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { confirmRun, declineRun, startRun } from "./api/demo";
import type { DemoRunSummary } from "./types/demo";

vi.mock("./api/demo", () => ({
  startRun: vi.fn(),
  getRun: vi.fn(),
  confirmRun: vi.fn(),
  declineRun: vi.fn(),
}));

const awaitingRun: DemoRunSummary = {
  run_id: "run-1",
  status: "awaiting_confirmation",
  read_profile: "mock_world",
  selected_plan_id: "plan-1",
  plan_version: {
    version_number: 1,
    version_label: "v1",
    source_run_id: null,
    source_selected_plan_id: null,
  },
  plans: [
    {
      plan_id: "plan-1",
      status: "reviewed",
      selected: true,
      title: "Family science afternoon",
      summary: "Start with a family activity, then stop for a lighter dinner.",
      activity: {
        name: "Science House",
        category: "activity",
        address: "100 Museum Road",
        tags: ["child_friendly", "indoor"],
      },
      dining: {
        name: "Light Kitchen",
        category: "dining",
        address: "6 Healthy Lane",
        tags: ["lighter_options", "family_tables"],
      },
      timeline: [
        {
          sequence: 1,
          title: "Science visit",
          start_label: "14:00",
          end_label: "16:00",
          duration_minutes: 120,
        },
      ],
      route: {
        mode: "driving",
        distance_meters: 3200,
        duration_minutes: 18,
        summary: "Short walk between stops.",
      },
      feasibility: {
        is_feasible: true,
        reasons: ["Fits the afternoon time window."],
        warnings: [],
        total_duration_minutes: 270,
        route_duration_minutes: 18,
        queue_wait_minutes: 5,
      },
      proposed_actions: [],
      action_manifest: {
        source: "proposed_actions",
        action_count: 1,
        actions: [
          {
            action_ref: "draft_1_action_1",
            execution_order: 1,
            action_type: "reserve_restaurant",
            target_id: "green-table",
            payload_preview: { party_size: 3 },
            reason: "Lock the dinner table after confirmation.",
          },
        ],
      },
      confirmation: { status: "pending", action_count: 1 },
    },
    {
      plan_id: "plan-2",
      status: "reviewed",
      selected: false,
      title: "Park fallback",
      summary: "Outdoor play plus a quick coffee shop dinner.",
      activity: {
        name: "Riverside Park",
        category: "activity",
        address: "Riverside Walk",
        tags: [],
      },
      dining: {
        name: "Corner Cafe",
        category: "dining",
        address: "Coffee Street",
        tags: [],
      },
      timeline: [],
      route: null,
      feasibility: null,
      proposed_actions: [],
      action_manifest: {
        source: "none",
        action_count: 0,
        actions: [],
      },
      confirmation: { status: "pending", action_count: 0 },
    },
  ],
  action_count: 0,
  execution_status: null,
  feedback_status: null,
  error: null,
};

const awaitingAmapRun: DemoRunSummary = {
  ...awaitingRun,
  run_id: "run-amap",
  read_profile: "amap",
};

const completedRun: DemoRunSummary = {
  ...awaitingRun,
  status: "completed",
  action_count: 2,
  execution_status: "succeeded",
  feedback_status: "written",
  plans: [
    {
      ...awaitingRun.plans[0],
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
            reason: "Lock the dinner table after confirmation.",
          },
        ],
      },
      confirmation: { status: "confirmed", confirmed_by: "web-demo-user", action_count: 1 },
      execution: {
        status: "succeeded",
        succeeded_count: 2,
        failed_count: 0,
      },
      feedback: {
        status: "written",
        headline: "Execution complete",
        message: "Reservation and message steps finished.",
        completed_actions: [{ action_type: "reserve_restaurant", status: "succeeded" }],
        failed_actions: [],
        next_steps: ["Leave at 13:40."],
      },
    },
  ],
};

const declinedRun: DemoRunSummary = {
  ...awaitingRun,
  status: "declined",
  plans: [
    {
      ...awaitingRun.plans[0],
      status: "declined",
      confirmation: {
        status: "declined",
        declined_by: "web-demo-user",
        reason: "User chose not to continue.",
      },
    },
  ],
};

describe("App", () => {
  beforeEach(() => {
    vi.mocked(startRun).mockReset();
    vi.mocked(confirmRun).mockReset();
    vi.mocked(declineRun).mockReset();
  });

  it("renders the default prompt, default read profile, and start button", () => {
    render(<App />);

    expect(screen.getByRole("textbox")).toHaveValue(
      "\u4eca\u5929\u4e0b\u5348\u60f3\u548c\u7231\u4eba\u30015\u5c81\u7684\u5b69\u5b50\u51fa\u95e8\u73a9\u51e0\u4e2a\u5c0f\u65f6\uff0c\u522b\u79bb\u5bb6\u592a\u8fdc\u3002\u5b69\u5b50\u8981\u9002\u5408\u4eb2\u5b50\u6d3b\u52a8\uff0c\u7231\u4eba\u6700\u8fd1\u60f3\u5403\u6e05\u6de1\u4e00\u70b9\uff0c\u5e2e\u6211\u5b89\u6392\u4e00\u4e0b\u3002",
    );
    expect(screen.getByTestId("start-button")).toBeEnabled();
    expect(screen.getByTestId("read-profile-select")).toHaveValue("mock_world");
  });

  it("disables start when the request is empty", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.clear(screen.getByRole("textbox"));

    expect(screen.getByTestId("start-button")).toBeDisabled();
    expect(
      screen.getByText((_, element) => element?.classList.contains("validation-text") ?? false),
    ).toBeInTheDocument();
  });

  it("renders awaiting-confirmation status and plan details after successful start", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByRole("heading", { name: "Family science afternoon" })).toBeInTheDocument();
    expect(screen.getAllByText("awaiting_confirmation").length).toBeGreaterThan(0);
    expect(screen.getByTestId("plan-version")).toHaveTextContent("v1");
    expect(screen.getByText("Science House")).toBeInTheDocument();
    expect(screen.getByText("Light Kitchen")).toBeInTheDocument();
    expect(screen.getByText("Short walk between stops.")).toBeInTheDocument();
    expect(screen.getByText("green-table")).toBeInTheDocument();
    expect(screen.getByTestId("active-read-profile")).toHaveTextContent("Mock World");
  });

  it("does not render internal observability labels on the public page", async () => {
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    expect(screen.queryByText("Trace ID")).not.toBeInTheDocument();
  });

  it("switches plan tabs without calling the backend", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByRole("tab", { name: /Park fallback/ }));

    expect(screen.getByText("Riverside Park")).toBeInTheDocument();
    expect(screen.queryByText("Science House")).not.toBeInTheDocument();
  });

  it("confirms a selected plan and renders completed feedback", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(confirmRun).mockResolvedValue(completedRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByTestId("confirm-button"));

    expect(confirmRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(await screen.findByText("Execution complete")).toBeInTheDocument();
    expect(screen.getByText("Reservation and message steps finished.")).toBeInTheDocument();
  });

  it("declines a selected plan and hides confirm action", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(declineRun).mockResolvedValue(declinedRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));
    await user.click(await screen.findByTestId("decline-button"));

    expect(declineRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
  });

  it("renders API errors in user-readable form", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockRejectedValue(new Error("API connection failed."));
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/./)).toBeInTheDocument();
  });

  it("sends the selected read profile when starting a run", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingAmapRun);
    render(<App />);

    await user.selectOptions(screen.getByTestId("read-profile-select"), "amap");
    await user.click(screen.getByTestId("start-button"));

    expect(startRun).toHaveBeenCalledWith(
      expect.objectContaining({
        read_profile: "amap",
      }),
    );
  });

  it("shows AMAP as the active read profile and blocks confirmation for the read-only preview path", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingAmapRun);
    render(<App />);

    await user.click(screen.getByTestId("start-button"));

    expect(await screen.findByTestId("active-read-profile")).toHaveTextContent(
      "AMap \u53ea\u8bfb\u9884\u89c8",
    );
    expect(screen.getByTestId("amap-read-only-notice")).toHaveTextContent(
      "\u53ea\u8bfb\u9884\u89c8",
    );
    expect(screen.queryByTestId("confirm-button")).not.toBeInTheDocument();
    expect(screen.getByTestId("decline-button")).toBeEnabled();
    expect(screen.getByTestId("refresh-button")).toBeEnabled();
  });
});
