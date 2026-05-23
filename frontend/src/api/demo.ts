import type { DemoRunSummary, DemoStartRunRequest } from "../types/demo";

export class DemoApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "DemoApiError";
    this.status = status;
  }
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function startRun(input: DemoStartRunRequest): Promise<DemoRunSummary> {
  return request<DemoRunSummary>("/demo/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
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
  const url = `${API_BASE_URL}${path}`;
  let response: Response;

  try {
    response = init ? await fetch(url, init) : await fetch(url);
  } catch (error) {
    throw new DemoApiError(connectionMessage(error), 0);
  }

  if (!response.ok) {
    throw new DemoApiError(await responseMessage(response), response.status);
  }

  return (await response.json()) as T;
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

function localizedResponseMessage(message: string, status: number): string {
  const knownMessages: Record<string, string> = {
    "Run not found.": "\u672a\u627e\u5230\u5bf9\u5e94\u7684\u6f14\u793a\u8fd0\u884c\u3002",
    "Demo run was not found.": "\u672a\u627e\u5230\u5bf9\u5e94\u7684\u6f14\u793a\u8fd0\u884c\u3002",
    "AMAP read path is not configured for this environment.":
      "\u672c\u5730\u73af\u5883\u672a\u914d\u7f6e AMap \u53ea\u8bfb\u9884\u89c8\u6240\u9700\u7684\u5bc6\u94a5\u3002",
    "AMAP read-only demo runs cannot be confirmed.":
      "AMap \u53ea\u8bfb\u9884\u89c8\u8def\u5f84\u4e0d\u652f\u6301\u786e\u8ba4\u6267\u884c\u3002",
  };
  return knownMessages[message] ?? statusFallbackMessage(status);
}

function statusFallbackMessage(status: number): string {
  return `\u6f14\u793a\u8bf7\u6c42\u5931\u8d25\uff08HTTP ${status}\uff09\u3002`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
