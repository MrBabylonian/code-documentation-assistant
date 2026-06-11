import type { AnswerPayload, CitationPayload } from "@/lib/apiTypes";
import { AnswerCostFooter } from "@/components/AnswerCostFooter";
import { CitationChip } from "@/components/CitationChip";

export interface ConversationEntry {
  role: "user" | "assistant";
  text: string;
  answer: AnswerPayload | null; // populated for completed assistant turns
}

export function MessageList({
  entries,
  liveAnswerText,
  isStreaming,
  onOpenCitation,
}: {
  entries: ConversationEntry[];
  liveAnswerText: string;
  isStreaming: boolean;
  onOpenCitation: (citation: CitationPayload) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {entries.map((conversationEntry, entryIndex) => (
        <div
          key={entryIndex}
          className={
            conversationEntry.role === "user"
              ? "self-end rounded-lg bg-slate-800 px-4 py-2 text-sm"
              : "self-start text-sm leading-relaxed text-slate-200"
          }
        >
          <p className="whitespace-pre-wrap">{conversationEntry.text}</p>
          {conversationEntry.answer !== null && (
            <>
              {conversationEntry.answer.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {conversationEntry.answer.citations.map((citation, citationIndex) => (
                    <CitationChip key={citationIndex} citation={citation} onOpen={onOpenCitation} />
                  ))}
                </div>
              )}
              <AnswerCostFooter answer={conversationEntry.answer} />
            </>
          )}
        </div>
      ))}
      {isStreaming && (
        <div className="self-start text-sm leading-relaxed text-slate-300">
          <p className="whitespace-pre-wrap">
            {liveAnswerText}
            <span className="animate-pulse text-teal-400">▍</span>
          </p>
        </div>
      )}
    </div>
  );
}
