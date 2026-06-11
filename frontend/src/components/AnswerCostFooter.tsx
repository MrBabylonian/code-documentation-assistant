import type { AnswerPayload } from "@/lib/apiTypes";

export function AnswerCostFooter({ answer }: { answer: AnswerPayload }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-3 font-mono text-xs text-slate-500">
      <span>{answer.model_name}</span>
      <span>{`${answer.input_tokens} in / ${answer.output_tokens} out`}</span>
      <span>{`$${answer.estimated_cost_usd.toFixed(4)}`}</span>
      <span>{`${answer.latency_ms} ms`}</span>
      {answer.is_grounded ? (
        <span className="text-emerald-400">✓ grounded</span>
      ) : (
        <span className="text-amber-400">⚠ not fully grounded</span>
      )}
    </div>
  );
}
