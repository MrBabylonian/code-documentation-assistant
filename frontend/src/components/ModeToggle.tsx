import type { AnswerMode } from "@/lib/apiTypes";

const MODE_LABELS: Record<AnswerMode, string> = {
  agentic: "Agentic",
  single_shot: "Single-shot",
};

export function ModeToggle({
  mode,
  onModeChange,
  disabled,
}: {
  mode: AnswerMode;
  onModeChange: (nextMode: AnswerMode) => void;
  disabled: boolean;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded border border-slate-700 text-xs">
      {(Object.keys(MODE_LABELS) as AnswerMode[]).map((modeOption) => (
        <button
          key={modeOption}
          type="button"
          disabled={disabled}
          onClick={() => onModeChange(modeOption)}
          className={
            modeOption === mode
              ? "bg-teal-600 px-3 py-1.5 font-semibold text-slate-950"
              : "bg-slate-900 px-3 py-1.5 text-slate-400 hover:text-slate-200"
          }
        >
          {MODE_LABELS[modeOption]}
        </button>
      ))}
    </div>
  );
}
