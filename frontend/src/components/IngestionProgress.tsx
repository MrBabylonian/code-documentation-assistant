import type { IngestionStatus } from "@/lib/apiTypes";

const PIPELINE_STAGES: IngestionStatus[] = ["pending", "cloning", "parsing", "embedding", "indexing"];

export function IngestionProgress({ status }: { status: IngestionStatus }) {
  const activeStageIndex = PIPELINE_STAGES.indexOf(status);
  return (
    <ol className="flex items-center gap-2 text-xs">
      {PIPELINE_STAGES.map((stageName, stageIndex) => (
        <li
          key={stageName}
          className={
            stageIndex < activeStageIndex
              ? "text-slate-500"
              : stageIndex === activeStageIndex
                ? "animate-pulse font-semibold text-amber-400"
                : "text-slate-700"
          }
        >
          {stageName}
          {stageIndex < PIPELINE_STAGES.length - 1 && <span className="ml-2 text-slate-700">→</span>}
        </li>
      ))}
    </ol>
  );
}
