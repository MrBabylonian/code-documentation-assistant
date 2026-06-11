import type { TimelineEntry } from "@/lib/useAnswerStream";

const ENTRY_ICONS: Record<TimelineEntry["kind"], string> = {
  tool_call: "▸",
  tool_result: "✓",
  notice: "↻",
};

export function AgentTimeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <ul className="flex flex-col gap-1 font-mono text-xs">
      {entries.map((timelineEntry, entryIndex) => (
        <li key={entryIndex} className="flex items-baseline gap-2">
          <span className={timelineEntry.kind === "notice" ? "text-amber-400" : "text-teal-400"}>
            {ENTRY_ICONS[timelineEntry.kind]}
          </span>
          <span className="text-slate-300">{timelineEntry.label}</span>
          <span className="truncate text-slate-600">{timelineEntry.detail}</span>
        </li>
      ))}
    </ul>
  );
}
