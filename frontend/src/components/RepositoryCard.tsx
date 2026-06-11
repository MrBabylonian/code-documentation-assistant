import Link from "next/link";

import type { RepositoryResponse } from "@/lib/apiTypes";
import { IngestionProgress } from "@/components/IngestionProgress";

const TRANSITIONAL_STATUSES = new Set(["pending", "cloning", "parsing", "embedding", "indexing"]);

export function RepositoryCard({ repository }: { repository: RepositoryResponse }) {
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-slate-200">{repository.name}</span>
        <StatusPill status={repository.status} />
      </div>
      <div className="mt-3 text-sm text-slate-500">
        {repository.status === "ready" && (
          <p>
            {repository.indexed_file_count} files · {repository.indexed_chunk_count} chunks
          </p>
        )}
        {repository.status === "failed" && repository.error_message !== null && (
          <p className="text-red-400">{repository.error_message}</p>
        )}
        {TRANSITIONAL_STATUSES.has(repository.status) && (
          <IngestionProgress status={repository.status} />
        )}
      </div>
      {repository.status === "ready" && (
        <Link
          href={`/repositories/${repository.repository_id}`}
          className="mt-3 inline-block text-sm font-semibold text-teal-400 hover:text-teal-300"
        >
          Ask questions →
        </Link>
      )}
    </article>
  );
}

function StatusPill({ status }: { status: RepositoryResponse["status"] }) {
  const pillClass =
    status === "ready"
      ? "bg-emerald-950 text-emerald-400 border-emerald-800"
      : status === "failed"
        ? "bg-red-950 text-red-400 border-red-800"
        : "bg-amber-950 text-amber-400 border-amber-800 animate-pulse";
  return (
    <span className={`rounded-full border px-2 py-0.5 font-mono text-xs ${pillClass}`}>
      {status}
    </span>
  );
}
