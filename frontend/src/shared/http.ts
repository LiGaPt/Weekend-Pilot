export type FrontendApiErrorKind = "connection" | "http" | "stream_protocol" | "stream_event";

export class FrontendApiError extends Error {
  status: number;
  kind: FrontendApiErrorKind;

  constructor(message: string, status: number, kind: FrontendApiErrorKind = "http") {
    super(message);
    this.name = "DemoApiError";
    this.status = status;
    this.kind = kind;
  }
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
