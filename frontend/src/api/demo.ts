import type {
  DemoClarifyRunRequest,
  DemoReplanRunRequest,
  DemoRunStreamErrorEvent,
  DemoRunStreamProgressEvent,
  DemoRunStreamSummaryEvent,
  DemoRunSummary,
  DemoStartRunRequest,
} from "../types/demo";
import { API_BASE_URL, FrontendApiError } from "../shared/http";
import { readSseStream } from "./sse";

const INVALID_STREAM_MESSAGE = "\u6f14\u793a\u670d\u52a1\u8fd4\u56de\u4e86\u65e0\u6548\u7684\u5b9e\u65f6\u8fdb\u5ea6\u54cd\u5e94\u3002";
const GENERIC_STREAM_FAILURE_MESSAGE = "\u6f14\u793a\u8bf7\u6c42\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002";

export type DemoStartRunStreamHandlers = {
  onProgress?: (event: DemoRunStreamProgressEvent) => void;
};

export async function startRun(input: DemoStartRunRequest): Promise<DemoRunSummary> {
  return request<DemoRunSummary>("/demo/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function startRunStream(
  input: DemoStartRunRequest,
  handlers: DemoStartRunStreamHandlers = {},
): Promise<DemoRunSummary> {
  const response = await fetchResponse("/demo/runs/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.body) {
    throw new FrontendApiError(INVALID_STREAM_MESSAGE, effectiveStreamStatus(response.status));
  }

  for await (const frame of readSseStream(response.body)) {
    if (frame.event === "progress") {
      const payload = parseStreamEvent(frame.data);
      if (isProgressEvent(payload)) {
        handlers.onProgress?.(payload);
      }
      continue;
    }

    if (frame.event === "summary") {
      const payload = parseStreamEvent(frame.data);
      if (isSummaryEvent(payload)) {
        return payload.summary;
      }
      throw new FrontendApiError(INVALID_STREAM_MESSAGE, effectiveStreamStatus(response.status));
    }

    if (frame.event === "error") {
      const payload = parseStreamEvent(frame.data);
      if (isErrorEvent(payload)) {
        throw new FrontendApiError(
          localizedResponseMessage(payload.message, effectiveStreamStatus(response.status)),
          effectiveStreamStatus(response.status),
        );
      }
      throw new FrontendApiError(INVALID_STREAM_MESSAGE, effectiveStreamStatus(response.status));
    }
  }

  throw new FrontendApiError(GENERIC_STREAM_FAILURE_MESSAGE, effectiveStreamStatus(response.status));
}

export async function getRun(runId: string): Promise<DemoRunSummary> {
  return request<DemoRunSummary>(`/demo/runs/${encodeURIComponent(runId)}`);
}

export async function confirmRun(runId: string, planId?: string | null): Promise<DemoRunSummary> {
  return request<DemoRunSummary>(`/demo/runs/${encodeURIComponent(runId)}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId ?? null, confirmed_by: "web-demo-user" }),
  });
}

export async function clarifyRun(runId: string, input: DemoClarifyRunRequest): Promise<DemoRunSummary> {
  return request<DemoRunSummary>(`/demo/runs/${encodeURIComponent(runId)}/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function replanRun(runId: string, input: DemoReplanRunRequest): Promise<DemoRunSummary> {
  return request<DemoRunSummary>(`/demo/runs/${encodeURIComponent(runId)}/replan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function declineRun(runId: string, planId?: string | null): Promise<DemoRunSummary> {
  return request<DemoRunSummary>(`/demo/runs/${encodeURIComponent(runId)}/decline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_id: planId ?? null,
      declined_by: "web-demo-user",
      reason: "\u7528\u6237\u9009\u62e9\u6682\u4e0d\u7ee7\u7eed\u3002",
    }),
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchResponse(path, init);
  return (await response.json()) as T;
}

async function fetchResponse(path: string, init?: RequestInit): Promise<Response> {
  const url = `${API_BASE_URL}${path}`;
  let response: Response;

  try {
    response = init ? await fetch(url, init) : await fetch(url);
  } catch (error) {
    throw new FrontendApiError(connectionMessage(error), 0);
  }

  if (!response.ok) {
    throw new FrontendApiError(await responseMessage(response), response.status);
  }

  return response;
}

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as unknown;
    if (isRecord(body)) {
      const detail = body.detail;
      if (typeof detail === "string" && detail.trim()) {
        return localizedResponseMessage(detail, response.status);
      }
      if (isRecord(detail) && typeof detail.message === "string" && detail.message.trim()) {
        return localizedResponseMessage(detail.message, response.status);
      }
    }
  } catch {
    return statusFallbackMessage(response.status);
  }

  return statusFallbackMessage(response.status);
}

function connectionMessage(error: unknown): string {
  void error;
  return "\u65e0\u6cd5\u8fde\u63a5\u6f14\u793a\u670d\u52a1\uff0c\u8bf7\u786e\u8ba4\u540e\u7aef\u6b63\u5728\u8fd0\u884c\u3002";
}

function parseStreamEvent(payload: string): unknown {
  try {
    return JSON.parse(payload) as unknown;
  } catch {
    throw new FrontendApiError(INVALID_STREAM_MESSAGE, 500);
  }
}

function localizedResponseMessage(message: string, status: number): string {
  const knownMessages: Record<string, string> = {
    "Run not found.": "\u672a\u627e\u5230\u5bf9\u5e94\u7684\u6f14\u793a\u8fd0\u884c\u3002",
    "Demo run was not found.": "\u672a\u627e\u5230\u5bf9\u5e94\u7684\u6f14\u793a\u8fd0\u884c\u3002",
    "AMAP read path is not configured for this environment.":
      "\u672c\u5730\u73af\u5883\u672a\u914d\u7f6e\u5730\u56fe\u53ea\u8bfb\u9884\u89c8\u6240\u9700\u7684\u5bc6\u94a5\u3002",
    "AMAP read-only demo runs cannot be confirmed.":
      "\u5730\u56fe\u53ea\u8bfb\u9884\u89c8\u8def\u5f84\u4e0d\u652f\u6301\u786e\u8ba4\u6267\u884c\u3002",
    "Source run status does not allow clarification.":
      "\u5f53\u524d\u8fd0\u884c\u5df2\u4e0d\u80fd\u7ee7\u7eed\u8865\u5145\u4fe1\u606f\uff0c\u8bf7\u5237\u65b0\u72b6\u6001\u540e\u91cd\u8bd5\u3002",
    "Source run is missing session persistence for clarification.":
      "\u5f53\u524d\u8fd0\u884c\u7f3a\u5c11\u8865\u5145\u4fe1\u606f\u4f1a\u8bdd\uff0c\u8bf7\u91cd\u65b0\u5f00\u59cb\u89c4\u5212\u3002",
    "Source run session is unavailable for clarification.":
      "\u5f53\u524d\u8fd0\u884c\u7f3a\u5c11\u8865\u5145\u4fe1\u606f\u4f1a\u8bdd\uff0c\u8bf7\u91cd\u65b0\u5f00\u59cb\u89c4\u5212\u3002",
    "Source run user is unavailable for clarification.":
      "\u5f53\u524d\u8fd0\u884c\u7f3a\u5c11\u5173\u8054\u7528\u6237\uff0c\u8bf7\u91cd\u65b0\u5f00\u59cb\u89c4\u5212\u3002",
    "Source run status does not allow replanning.":
      "\u5f53\u524d\u8fd0\u884c\u8fd8\u4e0d\u80fd\u7ee7\u7eed\u8c03\u6574\u65b9\u6848\uff0c\u8bf7\u5237\u65b0\u72b6\u6001\u540e\u91cd\u8bd5\u3002",
    "Source run is missing session persistence for replanning.":
      "\u5f53\u524d\u8fd0\u884c\u7f3a\u5c11\u7ee7\u7eed\u89c4\u5212\u4f1a\u8bdd\uff0c\u8bf7\u91cd\u65b0\u5f00\u59cb\u89c4\u5212\u3002",
    "Source run session is unavailable for replanning.":
      "\u5f53\u524d\u8fd0\u884c\u7f3a\u5c11\u7ee7\u7eed\u89c4\u5212\u4f1a\u8bdd\uff0c\u8bf7\u91cd\u65b0\u5f00\u59cb\u89c4\u5212\u3002",
    "Source run user is unavailable for replanning.":
      "\u5f53\u524d\u8fd0\u884c\u7f3a\u5c11\u5173\u8054\u7528\u6237\uff0c\u8bf7\u91cd\u65b0\u5f00\u59cb\u89c4\u5212\u3002",
  };
  return knownMessages[message] ?? statusFallbackMessage(status);
}

function effectiveStreamStatus(status: number): number {
  return status >= 400 ? status : 500;
}

function statusFallbackMessage(status: number): string {
  return `\u6f14\u793a\u8bf7\u6c42\u5931\u8d25\uff08HTTP ${status}\uff09\u3002`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isProgressEvent(value: unknown): value is DemoRunStreamProgressEvent {
  return (
    isRecord(value) &&
    typeof value.event_index === "number" &&
    typeof value.run_id === "string" &&
    isRecord(value.progress)
  );
}

function isSummaryEvent(value: unknown): value is DemoRunStreamSummaryEvent {
  return (
    isRecord(value) &&
    typeof value.event_index === "number" &&
    isRecord(value.summary) &&
    typeof value.summary.run_id === "string"
  );
}

function isErrorEvent(value: unknown): value is DemoRunStreamErrorEvent {
  return (
    isRecord(value) &&
    typeof value.event_index === "number" &&
    (typeof value.run_id === "string" || value.run_id === null) &&
    typeof value.message === "string" &&
    value.message.trim().length > 0
  );
}
