import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/lib/apiClient";
import { AnswerStreamReader } from "@/lib/answerStream";
import { useAnswerStream } from "@/lib/useAnswerStream";

function sseResponse(frames: string[]): Response {
  return new Response(new TextEncoder().encode(frames.join("")), {
    headers: { "content-type": "text/event-stream" },
  });
}

const HAPPY_FRAMES = [
  'data: {"kind":"tool_call","tool_name":"search_code","arguments":{"query":"auth"}}\n\n',
  'data: {"kind":"tool_result","tool_name":"search_code","summary":"<evidence …>"}\n\n',
  'data: {"kind":"answer_token","text":"It is "}\n\n',
  'data: {"kind":"answer_restart","reason":"answer had no citations"}\n\n',
  'data: {"kind":"answer_token","text":"It is cited "}\n\n',
  'data: {"kind":"answer_completed","answer":{"text":"It is cited.","citations":[{"file_path":"src/auth.py","start_line":1,"end_line":2}],"is_grounded":true,"mode":"agentic","model_name":"m","input_tokens":10,"output_tokens":5,"estimated_cost_usd":0.001,"latency_ms":42}}\n\n',
];

describe("useAnswerStream", () => {
  it("consumes a full stream: timeline, restart clearing, completion", async () => {
    const apiClient = {
      streamAnswer: vi.fn().mockResolvedValue(sseResponse(HAPPY_FRAMES)),
    } as unknown as ApiClient;
    const { result } = renderHook(() => useAnswerStream(apiClient, new AnswerStreamReader()));

    // act flushes the stream's state updates before assertions (React 19 testing requirement)
    await act(async () => {
      await result.current.askQuestion("repo1", "where is auth?", "agentic", []);
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(false));
    expect(result.current.completedAnswer?.is_grounded).toBe(true);
    // restart cleared the first token; only post-restart text remains
    expect(result.current.liveAnswerText).toBe("It is cited ");
    const timelineKinds = result.current.timelineEvents.map((entry) => entry.kind);
    expect(timelineKinds).toEqual(["tool_call", "tool_result", "notice"]);
    expect(result.current.streamError).toBeNull();
  });

  it("captures error events", async () => {
    const apiClient = {
      streamAnswer: vi.fn().mockResolvedValue(
        sseResponse(['data: {"kind":"error","message":"repository not found"}\n\n']),
      ),
    } as unknown as ApiClient;
    const { result } = renderHook(() => useAnswerStream(apiClient, new AnswerStreamReader()));

    await act(async () => {
      await result.current.askQuestion("missing", "where?", "agentic", []);
    });

    await waitFor(() => expect(result.current.streamError).toBe("repository not found"));
  });
});
