import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RepositoryResponse } from "@/lib/apiTypes";
import { RepositoryCard } from "@/components/RepositoryCard";

function repositoryFixture(overrides: Partial<RepositoryResponse>): RepositoryResponse {
  return {
    repository_id: "abc123def456",
    github_url: "https://github.com/owner/repo",
    name: "owner/repo",
    status: "ready",
    error_message: null,
    indexed_file_count: 42,
    indexed_chunk_count: 314,
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z",
    ...overrides,
  };
}

describe("RepositoryCard", () => {
  it("links to the chat when ready and shows counts", () => {
    render(<RepositoryCard repository={repositoryFixture({})} />);
    expect(screen.getByRole("link", { name: /ask questions/i }).getAttribute("href")).toBe(
      "/repositories/abc123def456",
    );
    expect(screen.getByText(/314/)).toBeDefined();
  });

  it("shows the error message when failed", () => {
    render(
      <RepositoryCard
        repository={repositoryFixture({ status: "failed", error_message: "clone timed out" })}
      />,
    );
    expect(screen.getByText("clone timed out")).toBeDefined();
    expect(screen.queryByRole("link", { name: /ask questions/i })).toBeNull();
  });

  it("shows the progress stepper while transitional", () => {
    render(<RepositoryCard repository={repositoryFixture({ status: "embedding" })} />);
    // "embedding" also appears in the status pill, so scope the query to the stepper list.
    expect(within(screen.getByRole("list")).getByText(/embedding/i)).toBeDefined();
    expect(screen.queryByRole("link", { name: /ask questions/i })).toBeNull();
  });
});
