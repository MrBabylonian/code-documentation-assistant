"use client";

import { useCallback, useState } from "react";

import type { ApiClient } from "@/lib/apiClient";
import type { AnswerStreamReader } from "@/lib/answerStream";
import type { AnswerMode, AnswerPayload, ChatTurnPayload } from "@/lib/apiTypes";

export interface TimelineEntry {
  kind: "tool_call" | "tool_result" | "notice";
  label: string;
  detail: string;
}

const TIMELINE_DETAIL_LENGTH_LIMIT = 80;

export function useAnswerStream(apiClient: ApiClient, streamReader: AnswerStreamReader) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [liveAnswerText, setLiveAnswerText] = useState("");
  const [timelineEvents, setTimelineEvents] = useState<TimelineEntry[]>([]);
  const [completedAnswer, setCompletedAnswer] = useState<AnswerPayload | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  const resetLiveState = useCallback(() => {
    setLiveAnswerText("");
    setTimelineEvents([]);
    setCompletedAnswer(null);
    setStreamError(null);
  }, []);

  const askQuestion = useCallback(
    async (
      repositoryId: string,
      question: string,
      mode: AnswerMode,
      history: ChatTurnPayload[],
    ) => {
      resetLiveState();
      setIsStreaming(true);
      try {
        const streamResponse = await apiClient.streamAnswer(repositoryId, question, mode, history);
        for await (const streamEvent of streamReader.read(streamResponse)) {
          switch (streamEvent.kind) {
            case "answer_token":
              setLiveAnswerText((previousText) => previousText + streamEvent.text);
              break;
            case "tool_call":
              setTimelineEvents((previousEntries) => [
                ...previousEntries,
                {
                  kind: "tool_call",
                  label: streamEvent.tool_name,
                  detail: JSON.stringify(streamEvent.arguments).slice(0, TIMELINE_DETAIL_LENGTH_LIMIT),
                },
              ]);
              break;
            case "tool_result":
              setTimelineEvents((previousEntries) => [
                ...previousEntries,
                {
                  kind: "tool_result",
                  label: streamEvent.tool_name,
                  detail: streamEvent.summary.slice(0, TIMELINE_DETAIL_LENGTH_LIMIT),
                },
              ]);
              break;
            case "answer_restart":
              setLiveAnswerText("");
              setTimelineEvents((previousEntries) => [
                ...previousEntries,
                { kind: "notice", label: "retry", detail: streamEvent.reason },
              ]);
              break;
            case "answer_completed":
              setCompletedAnswer(streamEvent.answer);
              break;
            case "error":
              setStreamError(streamEvent.message);
              break;
          }
        }
      } catch (streamFailure) {
        setStreamError(streamFailure instanceof Error ? streamFailure.message : "stream failed");
      } finally {
        setIsStreaming(false);
      }
    },
    [apiClient, streamReader, resetLiveState],
  );

  return {
    askQuestion,
    isStreaming,
    liveAnswerText,
    timelineEvents,
    completedAnswer,
    streamError,
    resetLiveState,
  };
}
