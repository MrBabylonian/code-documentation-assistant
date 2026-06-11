"use client";

import { useState } from "react";

import type { ApiClient } from "@/lib/apiClient";

const GITHUB_URL_PATTERN = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(\.git)?\/?$/;

export function RepositoryForm({
  apiClient,
  onIngestStarted,
}: {
  apiClient: ApiClient;
  onIngestStarted: () => void;
}) {
  const [githubUrl, setGithubUrl] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submitRepository(formEvent: React.FormEvent) {
    formEvent.preventDefault();
    if (!GITHUB_URL_PATTERN.test(githubUrl.trim())) {
      setFormError("Enter a public github.com repository URL, e.g. https://github.com/owner/repo");
      return;
    }
    setFormError(null);
    setIsSubmitting(true);
    try {
      await apiClient.ingestRepository(githubUrl.trim());
      setGithubUrl("");
      onIngestStarted();
    } catch (submitFailure) {
      setFormError(submitFailure instanceof Error ? submitFailure.message : "ingestion failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={submitRepository} className="flex flex-col gap-2">
      <div className="flex gap-3">
        <input
          value={githubUrl}
          onChange={(changeEvent) => setGithubUrl(changeEvent.target.value)}
          placeholder="https://github.com/owner/repo"
          className="flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-sm
                     placeholder:text-slate-600 focus:border-teal-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-teal-600 px-5 py-2 text-sm font-semibold text-slate-950
                     hover:bg-teal-500 disabled:opacity-50"
        >
          {isSubmitting ? "Ingesting…" : "Ingest"}
        </button>
      </div>
      {formError !== null && <p className="text-sm text-red-400">{formError}</p>}
    </form>
  );
}
