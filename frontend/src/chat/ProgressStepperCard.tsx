import { CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import type { AssistantProgressCardItem } from "./thread";

type ProgressStepperCardProps = {
  item: AssistantProgressCardItem;
};

export function ProgressStepperCard({ item }: ProgressStepperCardProps) {
  const [completedOpen, setCompletedOpen] = useState(false);

  return (
    <article className="thread-row thread-row-assistant">
      <div className="thread-bubble thread-bubble-assistant progress-stepper-card" data-testid="progress-stepper-card">
        <div className="assistant-card-header progress-stepper-header">
          <div>
            <p className="thread-label">\u5f53\u524d\u8fdb\u5ea6</p>
            <h2>{item.currentLabel}</h2>
          </div>
          <span className="thread-badge progress-stepper-stage">\u5f53\u524d\u6b65\u9aa4</span>
        </div>

        <section className="progress-step-current" aria-label="\u5f53\u524d\u6b65\u9aa4">
          <div className="progress-step-current-marker" aria-hidden="true">
            <CheckCircle2 size={18} />
          </div>
          <div className="progress-step-current-copy">
            <p className="progress-step-current-label">{item.currentLabel}</p>
            <p className="progress-step-current-summary">{item.currentSummary}</p>
          </div>
        </section>

        {item.completedSteps.length ? (
          <section className="progress-step-completed-shell">
            <button
              className="detail-disclosure-toggle progress-step-completed-toggle"
              type="button"
              onClick={() => setCompletedOpen((current) => !current)}
              data-testid="progress-completed-toggle"
              aria-expanded={completedOpen}
            >
              <span>
                {`\u5df2\u5b8c\u6210\u6b65\u9aa4 (${item.completedSteps.length})`}
              </span>
              {completedOpen ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
            </button>
            {completedOpen ? (
              <ol className="progress-step-completed-list" data-testid="progress-completed-list">
                {item.completedSteps.map((step) => (
                  <li key={`${item.runId}-${step.stage}`} className="progress-step-completed-item">
                    <p className="progress-step-completed-label">{step.label}</p>
                    <p className="progress-step-completed-summary">{step.summary}</p>
                  </li>
                ))}
              </ol>
            ) : null}
          </section>
        ) : null}
      </div>
    </article>
  );
}
