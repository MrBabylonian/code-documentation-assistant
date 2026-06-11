"use client";

import { useState } from "react";

export function QuestionInput({
  onSubmit,
  disabled,
}: {
  onSubmit: (question: string) => void;
  disabled: boolean;
}) {
  const [questionDraft, setQuestionDraft] = useState("");

  function submitQuestion() {
    const trimmedQuestion = questionDraft.trim();
    if (trimmedQuestion.length === 0 || disabled) return;
    onSubmit(trimmedQuestion);
    setQuestionDraft("");
  }

  return (
    <textarea
      value={questionDraft}
      onChange={(changeEvent) => setQuestionDraft(changeEvent.target.value)}
      onKeyDown={(keyEvent) => {
        if (keyEvent.key === "Enter" && !keyEvent.shiftKey) {
          keyEvent.preventDefault();
          submitQuestion();
        }
      }}
      disabled={disabled}
      rows={2}
      placeholder="Ask about this codebase… (Enter to send, Shift+Enter for a new line)"
      className="w-full resize-none rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm
                 placeholder:text-slate-600 focus:border-teal-500 focus:outline-none disabled:opacity-50"
    />
  );
}
