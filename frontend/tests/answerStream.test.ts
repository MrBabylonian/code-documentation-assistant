import { describe, expect, it } from "vitest";

import { AnswerStreamReader } from "@/lib/answerStream";
import type { AnswerStreamEvent } from "@/lib/apiTypes";

function responseFromChunks(chunks: Uint8Array[]): Response {
  const byteStream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  });
  return new Response(byteStream);
}

function utf8(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

async function readAll(response: Response): Promise<AnswerStreamEvent[]> {
  const collectedEvents: AnswerStreamEvent[] = [];
  for await (const streamEvent of new AnswerStreamReader().read(response)) {
    collectedEvents.push(streamEvent);
  }
  return collectedEvents;
}

describe("AnswerStreamReader", () => {
  it("parses frames split across chunks and multiple frames in one chunk", async () => {
    const events = await readAll(
      responseFromChunks([
        utf8('data: {"kind":"answer_token","te'), // frame split mid-JSON
        utf8('xt":"Hello "}\n\ndata: {"kind":"answer_token","text":"world"}\n\n'),
      ]),
    );
    expect(events).toEqual([
      { kind: "answer_token", text: "Hello " },
      { kind: "answer_token", text: "world" },
    ]);
  });

  it("survives a multibyte character split across byte chunks", async () => {
    const fullFrame = utf8('data: {"kind":"answer_token","text":"caffè"}\n\n');
    const splitPoint = fullFrame.length - 6; // inside the two-byte è sequence
    const events = await readAll(
      responseFromChunks([fullFrame.slice(0, splitPoint), fullFrame.slice(splitPoint)]),
    );
    expect(events).toEqual([{ kind: "answer_token", text: "caffè" }]);
  });

  it("ignores comment lines and normalizes CRLF", async () => {
    const events = await readAll(
      responseFromChunks([utf8(': ping\r\n\r\ndata: {"kind":"error","message":"nope"}\r\n\r\n')]),
    );
    expect(events).toEqual([{ kind: "error", message: "nope" }]);
  });

  it("joins multi-line data fields with a newline", async () => {
    const events = await readAll(
      responseFromChunks([utf8('data: {"kind":"answer_token",\ndata: "text":"x"}\n\n')]),
    );
    expect(events).toEqual([{ kind: "answer_token", text: "x" }]);
  });
});
