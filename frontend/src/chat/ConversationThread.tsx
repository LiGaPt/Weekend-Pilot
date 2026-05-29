import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  MapPinned,
  RefreshCw,
  Route,
  Send,
  Utensils,
  XCircle,
} from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import type { DemoPlanPreview } from "../types/demo";
import type {
  AssistantClarificationItem,
  AssistantPlanCardItem,
  AssistantResultCardItem,
  ConversationThreadItem,
  PlanSectionSummary,
} from "./thread";
import {
  actionExecutionLabel,
  actionLabel,
  actionManifestSourceLabel,
  candidateSummaryLines,
  display,
  distance,
  feedbackStatusLabel,
  feasibilityLabel,
  minutes,
  routeMode,
} from "./thread";

type ConversationThreadProps = {
  items: ConversationThreadItem[];
  activeRunId: string | null;
  requestState: string;
  clarificationReply: string;
  replanReply: string;
  canClarify: boolean;
  canConfirm: boolean;
  canDecline: boolean;
  canReplan: boolean;
  canRefresh: boolean;
  onSelectPlan: (planId: string) => void;
  onClarificationReplyChange: (value: string) => void;
  onClarificationSubmit: () => void;
  onReplanReplyChange: (value: string) => void;
  onReplanSubmit: () => void;
  onConfirm: () => void;
  onDecline: () => void;
  onRefresh: () => void;
};

export function ConversationThread({
  items,
  activeRunId,
  requestState,
  clarificationReply,
  replanReply,
  canClarify,
  canConfirm,
  canDecline,
  canReplan,
  canRefresh,
  onSelectPlan,
  onClarificationReplyChange,
  onClarificationSubmit,
  onReplanReplyChange,
  onReplanSubmit,
  onConfirm,
  onDecline,
  onRefresh,
}: ConversationThreadProps) {
  return (
    <div className="conversation-thread" aria-live="polite">
      {items.map((item) => {
        if (item.kind === "user_message") {
          return (
            <article key={item.id} className="thread-row thread-row-user">
              <div className="thread-bubble thread-bubble-user">
                <p className="thread-label">你的请求</p>
                <p>{item.text}</p>
              </div>
            </article>
          );
        }

        if (item.kind === "system_progress") {
          return (
            <article key={item.id} className="thread-row thread-row-system">
              <div className="thread-system-progress" data-testid="system-progress">
                <Loader2 className="spin" size={16} aria-hidden="true" />
                <span>{item.label}</span>
              </div>
            </article>
          );
        }

        if (item.kind === "assistant_clarification") {
          return (
            <ClarificationCard
              key={item.id}
              item={item}
              isActive={item.runId === activeRunId}
              requestState={requestState}
              reply={clarificationReply}
              canClarify={canClarify}
              canRefresh={canRefresh}
              onReplyChange={onClarificationReplyChange}
              onSubmit={onClarificationSubmit}
              onRefresh={onRefresh}
            />
          );
        }

        if (item.kind === "assistant_plan_card") {
          return (
            <PlanCard
              key={item.id}
              item={item}
              isActive={item.runId === activeRunId}
              requestState={requestState}
              replanReply={replanReply}
              canConfirm={canConfirm}
              canDecline={canDecline}
              canReplan={canReplan}
              canRefresh={canRefresh}
              onSelectPlan={onSelectPlan}
              onReplanReplyChange={onReplanReplyChange}
              onReplanSubmit={onReplanSubmit}
              onConfirm={onConfirm}
              onDecline={onDecline}
              onRefresh={onRefresh}
            />
          );
        }

        return <ResultCard key={item.id} item={item} />;
      })}
    </div>
  );
}

function ClarificationCard({
  item,
  isActive,
  requestState,
  reply,
  canClarify,
  canRefresh,
  onReplyChange,
  onSubmit,
  onRefresh,
}: {
  item: AssistantClarificationItem;
  isActive: boolean;
  requestState: string;
  reply: string;
  canClarify: boolean;
  canRefresh: boolean;
  onReplyChange: (value: string) => void;
  onSubmit: () => void;
  onRefresh: () => void;
}) {
  return (
    <article className="thread-row thread-row-assistant">
      <div className="thread-bubble thread-bubble-assistant">
        <div className="assistant-card-header">
          <div>
            <p className="thread-label">系统补充问题</p>
            <h2>还需要补充一点信息</h2>
          </div>
          <span className="thread-badge">{item.versionLabel}</span>
        </div>
        <p>{item.prompt}</p>
        <ul className="clarification-chip-list" data-testid="clarification-fields">
          {item.missingFields.map((field) => (
            <li key={field.id} className="clarification-chip">
              {field.label}
            </li>
          ))}
        </ul>
        {isActive ? (
          <div className="inline-form-block" data-testid="clarification-card">
            <label className="field-label" htmlFor="clarification-reply-input">
              补充说明
            </label>
            <textarea
              id="clarification-reply-input"
              value={reply}
              onChange={(event) => onReplyChange(event.target.value)}
              rows={4}
              disabled={requestState === "clarifying"}
              data-testid="clarification-reply-input"
            />
            <div className="button-row">
              <button
                className="primary-button"
                type="button"
                onClick={onSubmit}
                disabled={!canClarify}
                data-testid="clarification-submit-button"
              >
                {requestState === "clarifying" ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
                <span>{requestState === "clarifying" ? "提交中..." : "提交补充信息"}</span>
              </button>
            </div>
          </div>
        ) : null}
        <RunInfoDisclosure item={item} isActive={isActive} canRefresh={canRefresh} onRefresh={onRefresh} />
      </div>
    </article>
  );
}

function PlanCard({
  item,
  isActive,
  requestState,
  replanReply,
  canConfirm,
  canDecline,
  canReplan,
  canRefresh,
  onSelectPlan,
  onReplanReplyChange,
  onReplanSubmit,
  onConfirm,
  onDecline,
  onRefresh,
}: {
  item: AssistantPlanCardItem;
  isActive: boolean;
  requestState: string;
  replanReply: string;
  canConfirm: boolean;
  canDecline: boolean;
  canReplan: boolean;
  canRefresh: boolean;
  onSelectPlan: (planId: string) => void;
  onReplanReplyChange: (value: string) => void;
  onReplanSubmit: () => void;
  onConfirm: () => void;
  onDecline: () => void;
  onRefresh: () => void;
}) {
  return (
    <article className="thread-row thread-row-assistant">
      <div className="thread-bubble thread-bubble-assistant">
        <div className="assistant-card-header">
          <div>
            <p className="thread-label">推荐方案摘要</p>
            <h2>{item.title}</h2>
          </div>
          <div className="thread-badge-row">
            {item.visibleBadges.map((badge) => (
              <span key={badge} className="thread-badge">
                {badge}
              </span>
            ))}
          </div>
        </div>
        <p>{item.summary}</p>

        {item.alternativePlans.length > 1 ? (
          <div className="plan-chip-row" role="tablist" aria-label="可切换方案">
            {item.alternativePlans.map((plan) => (
              <button
                key={plan.planId}
                role="tab"
                type="button"
                aria-selected={plan.selected}
                className={plan.selected ? "plan-chip active" : "plan-chip"}
                disabled={!isActive || requestState === "replanning" || requestState === "confirming"}
                onClick={() => onSelectPlan(plan.planId)}
              >
                {plan.title}
              </button>
            ))}
          </div>
        ) : null}

        <div className="detail-disclosure-stack">
          {item.sections.map((section) => (
            <PlanSectionDisclosure key={section.id} section={section} plan={item.plan} />
          ))}
        </div>

        {item.readOnlyPreview ? (
          <div className="notice-banner" data-testid="amap-read-only-notice">
            <AlertCircle size={18} aria-hidden="true" />
            <span>AMap 只读预览会在确认前停止，不会执行任何写操作。</span>
          </div>
        ) : null}

        {isActive && (item.canConfirm || item.canDecline || item.canReplan) ? (
          <div className="chat-action-stack">
            <div className="button-row">
              {item.canConfirm && !item.readOnlyPreview ? (
                <button
                  className="primary-button"
                  type="button"
                  onClick={onConfirm}
                  disabled={!canConfirm}
                  data-testid="confirm-button"
                >
                  {requestState === "confirming" ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
                  <span>{requestState === "confirming" ? "确认中..." : "确认当前方案"}</span>
                </button>
              ) : null}
              {item.canDecline ? (
                <button
                  className="danger-button"
                  type="button"
                  onClick={onDecline}
                  disabled={!canDecline}
                  data-testid="decline-button"
                >
                  {requestState === "declining" ? <Loader2 className="spin" size={17} /> : <XCircle size={17} />}
                  <span>{requestState === "declining" ? "处理中..." : "暂不继续"}</span>
                </button>
              ) : null}
            </div>

            {item.canReplan ? (
              <div className="inline-form-block" data-testid="replan-panel">
                <label className="field-label" htmlFor="replan-reply-input">
                  继续调整方案
                </label>
                <textarea
                  id="replan-reply-input"
                  value={replanReply}
                  onChange={(event) => onReplanReplyChange(event.target.value)}
                  rows={4}
                  disabled={requestState === "replanning"}
                  data-testid="replan-reply-input"
                />
                <div className="button-row">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={onReplanSubmit}
                    disabled={!canReplan}
                    data-testid="replan-submit-button"
                  >
                    {requestState === "replanning" ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
                    <span>{requestState === "replanning" ? "调整中..." : "基于当前方案继续规划"}</span>
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        <RunInfoDisclosure item={item} isActive={isActive} canRefresh={canRefresh} onRefresh={onRefresh} />
      </div>
    </article>
  );
}

function ResultCard({ item }: { item: AssistantResultCardItem }) {
  const [timelineOpen, setTimelineOpen] = useState(false);

  return (
    <article className="thread-row thread-row-assistant">
      <div className="thread-bubble thread-bubble-assistant thread-bubble-result" data-testid="assistant-result-card">
        <div className="assistant-card-header">
          <div>
            <p className="thread-label">执行结果</p>
            <h2>{item.headline}</h2>
          </div>
          <span className="thread-badge">{item.outcomeLabel}</span>
        </div>
        {item.message ? <p>{item.message}</p> : null}

        <DisclosureBlock
          title="执行时间线"
          isOpen={timelineOpen}
          onToggle={() => setTimelineOpen((current) => !current)}
          testId="execution-timeline-toggle"
        >
          <section data-testid="execution-timeline">
            {item.executionWindow.startedAt || item.executionWindow.finishedAt ? (
              <dl className="compact-list execution-window-list">
                <div>
                  <dt>开始</dt>
                  <dd>{display(item.executionWindow.startedAt)}</dd>
                </div>
                <div>
                  <dt>结束</dt>
                  <dd>{display(item.executionWindow.finishedAt)}</dd>
                </div>
              </dl>
            ) : null}
            {item.executionTimeline.length ? (
              <ol className="execution-timeline-list">
                {item.executionTimeline.map((step) => (
                  <li key={`${step.executionOrder}-${step.actionRef ?? step.targetId ?? step.label}`}>
                    <span className="requirement">第 {step.executionOrder} 步</span>
                    <span className="action-type">{step.label}</span>
                    <span>{step.targetId || "暂无目标"}</span>
                    <span className="muted">{step.statusLabel}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="muted">已生成执行结果，但当前没有可展示的执行动作。</p>
            )}
          </section>
        </DisclosureBlock>

        <FeedbackList title="已完成动作" items={item.completedActions} />
        <FeedbackList title="失败动作" items={item.failedActions} />
        <TextList title="后续建议" items={item.nextSteps} />
      </div>
    </article>
  );
}

function PlanSectionDisclosure({ section, plan }: { section: PlanSectionSummary; plan: DemoPlanPreview }) {
  const [open, setOpen] = useState(false);

  return (
    <DisclosureBlock title={section.title} isOpen={open} onToggle={() => setOpen((current) => !current)}>
      {section.id === "timeline" ? <TimelineSection plan={plan} /> : null}
      {section.id === "activity_dining" ? <ActivityDiningSection plan={plan} /> : null}
      {section.id === "route_feasibility" ? <RouteFeasibilitySection plan={plan} /> : null}
      {section.id === "pre_confirmation_actions" ? <PreConfirmationActionsSection plan={plan} /> : null}
    </DisclosureBlock>
  );
}

function DisclosureBlock({
  title,
  isOpen,
  onToggle,
  children,
  testId,
}: {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section className="detail-disclosure">
      <button
        className="detail-disclosure-toggle"
        type="button"
        onClick={onToggle}
        data-testid={testId}
        aria-expanded={isOpen}
      >
        <span>{title}</span>
        {isOpen ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
      </button>
      {isOpen ? <div className="detail-disclosure-body">{children}</div> : null}
    </section>
  );
}

function TimelineSection({ plan }: { plan: DemoPlanPreview }) {
  return (
    <section>
      {plan.timeline?.length ? (
        <ol className="timeline-list">
          {plan.timeline.map((item, index) => (
            <li key={`${item.sequence ?? index}-${item.title ?? index}`}>
              <span className="time-range">
                {item.start_label || "待定"} - {item.end_label || "待定"}
              </span>
              <span className="timeline-title">{item.title || "未命名站点"}</span>
              <span className="muted">{minutes(item.duration_minutes)}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">暂无时间线。</p>
      )}
    </section>
  );
}

function ActivityDiningSection({ plan }: { plan: DemoPlanPreview }) {
  return (
    <div className="plan-grid">
      <CandidateSection title="活动" icon={<Activity size={18} />} lines={candidateSummaryLines(plan.activity)} />
      <CandidateSection title="餐厅" icon={<Utensils size={18} />} lines={candidateSummaryLines(plan.dining)} />
    </div>
  );
}

function CandidateSection({
  title,
  icon,
  lines,
}: {
  title: string;
  icon: ReactNode;
  lines: string[];
}) {
  return (
    <section className="candidate-section" aria-label={title}>
      <div className="section-heading">
        {icon}
        <h3>{title}</h3>
      </div>
      {lines.length ? (
        <ul className="candidate-line-list">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">暂无。</p>
      )}
    </section>
  );
}

function RouteFeasibilitySection({ plan }: { plan: DemoPlanPreview }) {
  return (
    <div className="detail-grid-two">
      <section>
        <div className="section-heading">
          <Route size={18} aria-hidden="true" />
          <h3>路线</h3>
        </div>
        <dl className="compact-list">
          <div>
            <dt>出行方式</dt>
            <dd>{display(routeMode(plan.route?.mode))}</dd>
          </div>
          <div>
            <dt>距离</dt>
            <dd>{distance(plan.route?.distance_meters)}</dd>
          </div>
          <div>
            <dt>时长</dt>
            <dd>{minutes(plan.route?.duration_minutes)}</dd>
          </div>
          <div>
            <dt>摘要</dt>
            <dd>{display(plan.route?.summary)}</dd>
          </div>
        </dl>
      </section>
      <section>
        <div className="section-heading">
          <CheckCircle2 size={18} aria-hidden="true" />
          <h3>可执行性</h3>
        </div>
        <dl className="compact-list">
          <div>
            <dt>结果</dt>
            <dd>{feasibilityLabel(plan.feasibility?.is_feasible)}</dd>
          </div>
          <div>
            <dt>总时长</dt>
            <dd>{minutes(plan.feasibility?.total_duration_minutes)}</dd>
          </div>
          <div>
            <dt>路线耗时</dt>
            <dd>{minutes(plan.feasibility?.route_duration_minutes)}</dd>
          </div>
          <div>
            <dt>排队等待</dt>
            <dd>{minutes(plan.feasibility?.queue_wait_minutes)}</dd>
          </div>
        </dl>
        <TextList title="依据" items={plan.feasibility?.reasons ?? []} />
        <TextList title="提醒" items={plan.feasibility?.warnings ?? []} />
      </section>
    </div>
  );
}

function PreConfirmationActionsSection({ plan }: { plan: DemoPlanPreview }) {
  return (
    <section>
      <div className="section-heading">
        <MapPinned size={18} aria-hidden="true" />
        <h3>确认前动作</h3>
      </div>
      <p className="helper-text">{actionManifestSourceLabel(plan.action_manifest)}</p>
      {plan.action_manifest.actions.length ? (
        <ul className="action-list">
          {plan.action_manifest.actions.map((action, index) => (
            <li key={`${action.action_ref ?? action.action_type ?? index}`}>
              <span className="action-type">{actionLabel(action.action_type) || "动作"}</span>
              <span>{action.target_id || "暂无目标"}</span>
              <span className="muted">{action.reason || "暂无说明。"}</span>
              <span className="requirement">{actionExecutionLabel(action.execution_order)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">暂无待执行动作。</p>
      )}
    </section>
  );
}

function FeedbackList({ title, items }: { title: string; items: Record<string, unknown>[] }) {
  if (!items.length) {
    return (
      <div className="feedback-block">
        <h3>{title}</h3>
        <p className="muted">暂无。</p>
      </div>
    );
  }

  return (
    <div className="feedback-block">
      <h3>{title}</h3>
      <ul className="feedback-list">
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>
            <span>{actionLabel(readString(item.action_type) || readString(item.tool_name)) || "动作"}</span>
            <span>{feedbackStatusLabel(readString(item.status)) || "未知"}</span>
            <span className="muted">
              {readString(item.message) || readString(item.target_label) || readString(item.target_id) || "暂无详情。"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TextList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="text-list-block">
      <h4>{title}</h4>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">暂无。</p>
      )}
    </div>
  );
}

function RunInfoDisclosure({
  item,
  isActive,
  canRefresh,
  onRefresh,
}: {
  item: AssistantClarificationItem | AssistantPlanCardItem;
  isActive: boolean;
  canRefresh: boolean;
  onRefresh: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <section className="run-info-block">
      <button
        className="detail-disclosure-toggle run-info-toggle"
        type="button"
        onClick={() => setOpen((current) => !current)}
        data-testid="run-info-toggle"
        aria-expanded={open}
      >
        <span>运行信息</span>
        {open ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
      </button>
      {open ? (
        <div className="run-info-body">
          <dl className="compact-list">
            <div>
              <dt>运行 ID</dt>
              <dd className="mono" data-testid="run-id">
                {item.hiddenRunInfo.runId}
              </dd>
            </div>
            <div>
              <dt>方案版本</dt>
              <dd data-testid="plan-version">{item.hiddenRunInfo.versionLabel}</dd>
            </div>
            <div>
              <dt>读取路径</dt>
              <dd data-testid="active-read-profile">{item.hiddenRunInfo.readProfileLabel}</dd>
            </div>
          </dl>
          {isActive ? (
            <div className="button-row">
              <button
                className="secondary-button"
                type="button"
                onClick={onRefresh}
                disabled={!canRefresh}
                data-testid="refresh-button"
              >
                <RefreshCw size={17} />
                <span>刷新当前状态</span>
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function readString(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}
