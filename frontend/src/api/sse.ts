export type SseFrame = {
  event: string | null;
  data: string;
};

export async function* readSseStream(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseFrame, void, undefined> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let pendingCarriageReturn = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += normalizeChunk(decoder.decode(value, { stream: true }));
      buffer = yield* flushCompleteFrames(buffer);
    }

    buffer += normalizeChunk(decoder.decode());

    if (pendingCarriageReturn) {
      buffer += "\n";
      pendingCarriageReturn = false;
    }

    const frame = parseFrame(buffer);
    if (frame) {
      yield frame;
    }
  } finally {
    reader.releaseLock();
  }

  function normalizeChunk(chunk: string) {
    let text = chunk;
    let normalized = "";

    if (pendingCarriageReturn) {
      if (text.startsWith("\n")) {
        text = text.slice(1);
      }
      normalized += "\n";
      pendingCarriageReturn = false;
    }

    if (text.endsWith("\r")) {
      pendingCarriageReturn = true;
      text = text.slice(0, -1);
    }

    normalized += text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    return normalized;
  }
}

function* flushCompleteFrames(buffer: string): Generator<SseFrame, string, undefined> {
  let nextBuffer = buffer;

  while (true) {
    const separatorIndex = nextBuffer.indexOf("\n\n");
    if (separatorIndex < 0) {
      break;
    }

    const rawFrame = nextBuffer.slice(0, separatorIndex);
    nextBuffer = nextBuffer.slice(separatorIndex + 2);

    const frame = parseFrame(rawFrame);
    if (frame) {
      yield frame;
    }
  }

  return nextBuffer;
}

function parseFrame(rawFrame: string): SseFrame | null {
  if (!rawFrame.trim()) {
    return null;
  }

  let event: string | null = null;
  const dataLines: string[] = [];

  for (const line of rawFrame.split("\n")) {
    if (!line || line.startsWith(":")) {
      continue;
    }

    const separatorIndex = line.indexOf(":");
    const field = separatorIndex >= 0 ? line.slice(0, separatorIndex) : line;
    let value = separatorIndex >= 0 ? line.slice(separatorIndex + 1) : "";

    if (value.startsWith(" ")) {
      value = value.slice(1);
    }

    if (field === "event") {
      event = value || null;
      continue;
    }

    if (field === "data") {
      dataLines.push(value);
    }
  }

  if (!dataLines.length) {
    return null;
  }

  return {
    event,
    data: dataLines.join("\n"),
  };
}
