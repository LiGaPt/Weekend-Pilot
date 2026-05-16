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
      reason: "用户选择暂不继续。",
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
  return "无法连接演示服务，请确认后端正在运行。";
}

function localizedResponseMessage(message: string, status: number): string {
  const knownMessages: Record<string, string> = {
    "Run not found.": "未找到对应的演示运行。",
    "Demo run was not found.": "未找到对应的演示运行。",
  };
  return knownMessages[message] ?? statusFallbackMessage(status);
}

function statusFallbackMessage(status: number): string {
  return `演示请求失败（HTTP ${status}）。`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
