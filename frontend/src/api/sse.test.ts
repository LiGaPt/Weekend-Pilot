import { describe, expect, it } from "vitest";
import { readSseStream } from "./sse";

function encode(value: string) {
  return new TextEncoder().encode(value);
}

function createStream(chunks: string[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encode(chunk));
      }
      controller.close();
    },
  });
}

async function collectFrames(chunks: string[]) {
  const frames = [];

  for await (const frame of readSseStream(createStream(chunks))) {
    frames.push(frame);
  }

  return frames;
}

describe("readSseStream", () => {
  it("parses a single chunk with one frame", async () => {
    const frames = await collectFrames([
      'event: progress\ndata: {"event_index":1,"run_id":"run-1"}\n\n',
    ]);

    expect(frames).toEqual([
      {
        event: "progress",
        data: '{"event_index":1,"run_id":"run-1"}',
      },
    ]);
  });

  it("parses frames split across chunks", async () => {
    const frames = await collectFrames([
      'event: progress\ndata: {"event_in',
      'dex":1,"run_id":"run-1"}\n\n',
    ]);

    expect(frames).toEqual([
      {
        event: "progress",
        data: '{"event_index":1,"run_id":"run-1"}',
      },
    ]);
  });

  it("normalizes CRLF line endings", async () => {
    const frames = await collectFrames([
      'event: summary\r\ndata: {"event_index":2}\r\n\r\n',
    ]);

    expect(frames).toEqual([
      {
        event: "summary",
        data: '{"event_index":2}',
      },
    ]);
  });

  it("joins multi-line data fields", async () => {
    const frames = await collectFrames([
      "event: error\ndata: first line\ndata: second line\n\n",
    ]);

    expect(frames).toEqual([
      {
        event: "error",
        data: "first line\nsecond line",
      },
    ]);
  });

  it("ignores comments and unsupported fields", async () => {
    const frames = await collectFrames([
      ": keepalive\nid: 1\nretry: 3000\nevent: progress\ndata: ok\n\n",
    ]);

    expect(frames).toEqual([
      {
        event: "progress",
        data: "ok",
      },
    ]);
  });
});
