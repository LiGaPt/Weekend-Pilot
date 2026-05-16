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
      reason: "User chose not to continue.",
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
        return detail;
      }
      if (isRecord(detail) && typeof detail.message === "string" && detail.message.trim()) {
        return detail.message;
      }
    }
  } catch {
    return `API request failed with status ${response.status}.`;
  }

  return `API request failed with status ${response.status}.`;
}

function connectionMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return `API connection failed: ${error.message}`;
  }
  return "API connection failed. Check that the backend is running at the configured URL.";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
