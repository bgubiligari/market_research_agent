import type { Handle, Snapshot } from "./contracts";
export const terminal = new Set([
  "completed",
  "partial",
  "failed",
  "cancelled",
  "expired",
]);
export const storageKey = "project3a.run";
export class ApiError extends Error {
  constructor(public status: number) {
    super(
      (
        {
          404: "This temporary run is unavailable. The API may have restarted.",
          410: "This run expired. Start a new comparison.",
          409: "The run changed. Refresh its status and try again.",
          422: "Check the company inputs and scope.",
          429: "The local API already has an active run or is at capacity.",
          502: "The local research API is unavailable.",
        } as Record<number, string>
      )[status] || "The request failed. Please retry.",
    );
  }
}
export async function api<T>(
  path: string,
  handle?: Handle,
  body?: unknown,
  key?: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`/api/v1/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(handle ? { "X-Run-Token": handle.run_token } : {}),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(key ? { "Idempotency-Key": key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(20000)])
      : AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.json();
}
export function decimal(value: string | number | null): number | null {
  if (
    value === null ||
    (typeof value === "string" &&
      !/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(value))
  )
    return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
export function safeUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}
// Incremental framing handles split UTF-8/chunks, CRLF, comments and multi-line data.
export class SSEParser {
  private buffer = "";
  feed(chunk: string): { id: number; data: Snapshot }[] {
    this.buffer += chunk;
    const events: { id: number; data: Snapshot }[] = [];
    let match: RegExpExecArray | null;
    while ((match = /\r?\n\r?\n/.exec(this.buffer))) {
      const frame = this.buffer.slice(0, match.index);
      this.buffer = this.buffer.slice(match.index + match[0].length);
      let id = "";
      const data: string[] = [];
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith("id:")) id = line.slice(3).trim();
        if (line.startsWith("data:"))
          data.push(line.slice(5).replace(/^ /, ""));
      }
      if (data.length && /^\d+$/.test(id))
        events.push({ id: Number(id), data: JSON.parse(data.join("\n")) });
    }
    return events;
  }
}
export async function stream(
  handle: Handle,
  cursor: number,
  signal: AbortSignal,
  onEvent: (snapshot: Snapshot, id: number) => void,
) {
  const response = await fetch(`/api/v1/runs/${handle.run_id}/events`, {
    headers: {
      "X-Run-Token": handle.run_token,
      "Last-Event-ID": String(cursor),
    },
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError(response.status);
  if (!response.body) throw new Error("Stream unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();
  try {
    while (true) {
      // Heartbeats arrive every 15 seconds. A silent connection is retried.
      const idle = setTimeout(() => void reader.cancel(), 45000);
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } finally {
        clearTimeout(idle);
      }
      const { done, value } = chunk;
      if (done) break;
      for (const e of parser.feed(decoder.decode(value, { stream: true })))
        onEvent(e.data, e.id);
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
