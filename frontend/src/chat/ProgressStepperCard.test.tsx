import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ProgressStepperCard } from "./ProgressStepperCard";
import type { AssistantProgressCardItem } from "./thread";

const item: AssistantProgressCardItem = {
  id: "run-1-progress",
  kind: "assistant_progress_card",
  runId: "run-1",
  currentStage: "ready_for_confirmation",
  currentLabel: "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
  currentSummary: "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d",
  completedCollapsedByDefault: true,
  completedSteps: [
    {
      stage: "searching_activities",
      label: "\u6b63\u5728\u67e5\u8be2\u6e38\u73a9\u5730\u70b9",
      summary: "\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8",
    },
    {
      stage: "searching_dining",
      label: "\u6b63\u5728\u67e5\u8be2\u9910\u5385",
      summary: "\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385",
    },
  ],
};

describe("ProgressStepperCard", () => {
  it("renders the current step and keeps completed steps collapsed by default", async () => {
    const user = userEvent.setup();
    render(<ProgressStepperCard item={item} />);

    expect(screen.getByTestId("progress-stepper-card")).toBeInTheDocument();
    expect(screen.getByText("当前进度")).toBeInTheDocument();
    expect(screen.getByText("当前步骤")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "当前步骤" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d" })).toBeInTheDocument();
    expect(screen.getAllByText("\u63a8\u8350\u65b9\u6848\u5df2\u51c6\u5907\u597d").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "已完成步骤 (2)" })).toBeInTheDocument();
    expect(screen.queryAllByText(/\\u|\\U/)).toHaveLength(0);
    expect(screen.queryByText("\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8")).not.toBeInTheDocument();
    expect(screen.queryByText("\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("progress-completed-toggle"));

    expect(screen.getByTestId("progress-completed-list")).toBeInTheDocument();
    expect(screen.getByText("\u5df2\u627e\u5230 5 \u4e2a\u6d3b\u52a8")).toBeInTheDocument();
    expect(screen.getByText("\u5df2\u627e\u5230 5 \u4e2a\u9910\u5385")).toBeInTheDocument();
  });
});
