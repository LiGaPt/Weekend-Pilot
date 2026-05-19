import { API_BASE_URL, DemoApiError } from "../api/demo";
import type { InternalObservabilityRunSummary } from "./types";

export async function getObservabilityRun(runId: string): Promise<InternalObservabilityRunSummary> {
  return request<InternalObservabilityRunSummary>(
    `/internal/runs/${encodeURIComponent(runId)}/observability`,
  );
}

async function request<T>(path: string): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let response: Response;

  try {
    response = await fetch(url);
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
  return "无法连接内部观测服务，请确认后端正在运行。";
}

function localizedResponseMessage(message: string, status: number): string {
  const knownMessages: Record<string, string> = {
    "Observability run was not found.": "未找到对应的内部观测运行。",
  };
  return knownMessages[message] ?? statusFallbackMessage(status);
}

function statusFallbackMessage(status: number): string {
  return `内部观测请求失败（HTTP ${status}）。`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
