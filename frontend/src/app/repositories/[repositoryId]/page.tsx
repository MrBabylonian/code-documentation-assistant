"use client";

import { use, useMemo, useState } from "react";

import { ApiClient } from "@/lib/apiClient";
import { AnswerStreamReader } from "@/lib/answerStream";
import type { AnswerMode, CitationPayload, FileSpanResponse } from "@/lib/apiTypes";
import { useAnswerStream } from "@/lib/useAnswerStream";
import { AgentTimeline } from "@/components/AgentTimeline";
import { MessageList, type ConversationEntry } from "@/components/MessageList";
import { ModeToggle } from "@/components/ModeToggle";
import { CodeSpanView } from "@/components/CodeSpanView";
import { QuestionInput } from "@/components/QuestionInput";

const HISTORY_TURNS_SENT = 6;

export default function ChatPage({ params }: { params: Promise<{ repositoryId: string }> }) {
  const { repositoryId } = use(params);
  const apiClient = useMemo(
    () => new ApiClient(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"),
    [],
  );
  const streamReader = useMemo(() => new AnswerStreamReader(), []);
  const answerStream = useAnswerStream(apiClient, streamReader);

  const [conversationEntries, setConversationEntries] = useState<ConversationEntry[]>([]);
  const [answerMode, setAnswerMode] = useState<AnswerMode>("agentic");
  const [openFileSpan, setOpenFileSpan] = useState<FileSpanResponse | null>(null);

  async function submitQuestion(question: string) {
    const historyPayload = conversationEntries
      .slice(-HISTORY_TURNS_SENT)
      .map((entry) => ({ role: entry.role, text: entry.text }));
    setConversationEntries((previousEntries) => [
      ...previousEntries,
      { role: "user", text: question, answer: null },
    ]);
    await answerStream.askQuestion(repositoryId, question, answerMode, historyPayload);
  }

  // append the assistant turn exactly once per completed answer
  const completedAnswer = answerStream.completedAnswer;
  if (
    completedAnswer !== null &&
    (conversationEntries.length === 0 ||
      conversationEntries[conversationEntries.length - 1].answer !== completedAnswer)
  ) {
    setConversationEntries((previousEntries) => [
      ...previousEntries,
      { role: "assistant", text: completedAnswer.text, answer: completedAnswer },
    ]);
    answerStream.resetLiveState();
  }

  async function openCitation(citation: CitationPayload) {
    const fileSpan = await apiClient.fetchFileSpan(
      repositoryId, citation.file_path, citation.start_line, citation.end_line,
    );
    if (fileSpan !== null) setOpenFileSpan(fileSpan);
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_380px]">
      <section className="flex flex-col gap-4">
        <MessageList
          entries={conversationEntries}
          liveAnswerText={answerStream.liveAnswerText}
          isStreaming={answerStream.isStreaming}
          onOpenCitation={openCitation}
        />
        {answerStream.streamError !== null && (
          <p className="text-sm text-red-400">{answerStream.streamError}</p>
        )}
        <div className="flex items-center gap-3">
          <ModeToggle
            mode={answerMode}
            onModeChange={setAnswerMode}
            disabled={answerStream.isStreaming}
          />
        </div>
        <QuestionInput onSubmit={(question) => void submitQuestion(question)}
                       disabled={answerStream.isStreaming} />
      </section>
      <aside className="flex flex-col gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Agent activity
          </h2>
          <AgentTimeline entries={answerStream.timelineEvents} />
        </div>
        {openFileSpan !== null && <CodeSpanView fileSpan={openFileSpan} />}
      </aside>
    </div>
  );
}
