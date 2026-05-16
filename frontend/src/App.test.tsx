import { render, screen, waitFor, within } from "@testing-library/react";
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
  trace_id: "trace-1",
  status: "awaiting_confirmation",
  selected_plan_id: "plan-1",
  plans: [
    {
      plan_id: "plan-1",
      status: "reviewed",
      selected: true,
      title: "Calm family afternoon",
      summary: "A gentle activity followed by lighter dining.",
      activity: {
        name: "Riverside Children Museum",
        category: "Family activity",
        address: "88 Riverside Road",
        tags: ["child-friendly", "indoor"],
      },
      dining: {
        name: "Green Table",
        category: "Light dining",
        address: "12 Garden Lane",
        tags: ["lighter meals"],
      },
      timeline: [
        {
          sequence: 1,
          title: "Museum visit",
          start_label: "14:00",
          end_label: "16:00",
          duration_minutes: 120,
        },
      ],
      route: {
        mode: "driving",
        distance_meters: 3200,
        duration_minutes: 18,
        summary: "Short drive between stops.",
      },
      feasibility: {
        is_feasible: true,
        reasons: ["Fits the afternoon window."],
        warnings: [],
        total_duration_minutes: 270,
        route_duration_minutes: 18,
        queue_wait_minutes: 5,
      },
      proposed_actions: [
        {
          action_type: "reserve_restaurant",
          target_id: "green-table",
          requires_confirmation: true,
          reason: "Secure dinner table.",
        },
      ],
      confirmation: { status: "pending", action_count: 1 },
    },
    {
      plan_id: "plan-2",
      status: "reviewed",
      selected: false,
      title: "Park and cafe backup",
      summary: "Outdoor activity with cafe fallback.",
      activity: { name: "City Park", category: "Outdoor", address: "Park Road", tags: [] },
      dining: { name: "Soft Spoon Cafe", category: "Cafe", address: "Cafe Street", tags: [] },
      timeline: [],
      route: null,
      feasibility: null,
      proposed_actions: [],
      confirmation: { status: "pending", action_count: 0 },
    },
  ],
  node_history: ["initialize_run", "wait_confirmation"],
  tool_event_count: 7,
  action_count: 0,
  execution_status: null,
  feedback_status: null,
  observability_status: "local_buffered",
  agent_roles: ["supervisor", "discovery", "dining"],
  error: null,
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
      confirmation: { status: "confirmed", confirmed_by: "web-demo-user", action_count: 1 },
      execution: {
        status: "succeeded",
        succeeded_count: 2,
        failed_count: 0,
      },
      feedback: {
        status: "written",
        headline: "Plan is ready",
        message: "Reservation and message were completed.",
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

  it("renders the default prompt and start button", () => {
    render(<App />);

    expect(screen.getByRole("textbox", { name: /^request$/i })).toHaveValue(
      "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter.",
    );
    expect(screen.getByRole("button", { name: /start planning/i })).toBeEnabled();
  });

  it("disables start when the request is empty", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.clear(screen.getByRole("textbox", { name: /^request$/i }));

    expect(screen.getByRole("button", { name: /start planning/i })).toBeDisabled();
    expect(screen.getByText(/enter a request/i)).toBeInTheDocument();
  });

  it("renders awaiting-confirmation status and plan details after successful start", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /start planning/i }));

    expect(await screen.findByRole("heading", { name: "Calm family afternoon" })).toBeInTheDocument();
    expect(screen.getAllByText("awaiting_confirmation").length).toBeGreaterThan(0);
    expect(screen.getByText("Riverside Children Museum")).toBeInTheDocument();
    expect(screen.getByText("Green Table")).toBeInTheDocument();
    expect(screen.getByText("Short drive between stops.")).toBeInTheDocument();
  });

  it("switches plan tabs without calling the backend", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /start planning/i }));
    await user.click(await screen.findByRole("tab", { name: /park and cafe backup/i }));

    expect(screen.getByText("City Park")).toBeInTheDocument();
    expect(screen.queryByText("Riverside Children Museum")).not.toBeInTheDocument();
  });

  it("confirms a selected plan and renders completed feedback", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(confirmRun).mockResolvedValue(completedRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /start planning/i }));
    await user.click(await screen.findByRole("button", { name: /confirm selected plan/i }));

    expect(confirmRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(await screen.findByText("Plan is ready")).toBeInTheDocument();
    expect(screen.getByText("Reservation and message were completed.")).toBeInTheDocument();
  });

  it("declines a selected plan and hides confirm action", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockResolvedValue(awaitingRun);
    vi.mocked(declineRun).mockResolvedValue(declinedRun);
    render(<App />);

    await user.click(screen.getByRole("button", { name: /start planning/i }));
    await user.click(await screen.findByRole("button", { name: /^decline$/i }));

    expect(declineRun).toHaveBeenCalledWith("run-1", "plan-1");
    expect(await screen.findByText("User chose not to continue.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /confirm selected plan/i })).not.toBeInTheDocument();
  });

  it("renders API errors in user-readable form", async () => {
    const user = userEvent.setup();
    vi.mocked(startRun).mockRejectedValue(new Error("API connection failed."));
    render(<App />);

    await user.click(screen.getByRole("button", { name: /start planning/i }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("API connection failed.")).toBeInTheDocument();
  });
});
