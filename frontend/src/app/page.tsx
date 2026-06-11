"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiClient } from "@/lib/apiClient";
import type { RepositoryResponse } from "@/lib/apiTypes";
import { RepositoryCard } from "@/components/RepositoryCard";
import { RepositoryForm } from "@/components/RepositoryForm";

const POLL_INTERVAL_MS = 2000;
const TRANSITIONAL_STATUSES = new Set(["pending", "cloning", "parsing", "embedding", "indexing"]);

export default function HomePage() {
  const apiClient = useMemo(
    () => new ApiClient(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"),
    [],
  );
  const [repositories, setRepositories] = useState<RepositoryResponse[]>([]);

  const refreshRepositories = useCallback(async () => {
    setRepositories(await apiClient.listRepositories());
  }, [apiClient]);

  useEffect(() => {
    async function loadInitialRepositories() {
      await refreshRepositories();
    }
    void loadInitialRepositories();
  }, [refreshRepositories]);

  const hasTransitionalRepository = repositories.some((repository) =>
    TRANSITIONAL_STATUSES.has(repository.status),
  );

  useEffect(() => {
    if (!hasTransitionalRepository) return;
    const pollTimer = setInterval(() => void refreshRepositories(), POLL_INTERVAL_MS);
    return () => clearInterval(pollTimer);
  }, [hasTransitionalRepository, refreshRepositories]);

  return (
    <div className="flex flex-col gap-8">
      <section>
        <h1 className="mb-1 text-xl font-semibold text-slate-100">Ingest a repository</h1>
        <p className="mb-4 text-sm text-slate-500">
          Paste a public GitHub URL — it gets cloned, parsed, and indexed for cited Q&amp;A.
        </p>
        <RepositoryForm apiClient={apiClient} onIngestStarted={() => void refreshRepositories()} />
      </section>
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {repositories.map((repository) => (
          <RepositoryCard key={repository.repository_id} repository={repository} />
        ))}
      </section>
    </div>
  );
}
