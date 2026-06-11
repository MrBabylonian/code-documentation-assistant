import type { CitationPayload } from "@/lib/apiTypes";

export function CitationChip({
  citation,
  onOpen,
}: {
  citation: CitationPayload;
  onOpen: (citation: CitationPayload) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      className="rounded border border-slate-700 bg-slate-900 px-2 py-0.5 font-mono text-xs
                 text-teal-300 hover:border-teal-600"
    >
      {`${citation.file_path}:${citation.start_line}-${citation.end_line}`}
    </button>
  );
}
