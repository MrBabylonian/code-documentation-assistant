import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/lib/apiClient";
import { RepositoryForm } from "@/components/RepositoryForm";

function stubApiClient(): ApiClient {
  return { ingestRepository: vi.fn().mockResolvedValue({ repository_id: "abc" }) } as unknown as ApiClient;
}

describe("RepositoryForm", () => {
  it("rejects a non-github URL without calling the API", async () => {
    const apiClient = stubApiClient();
    render(<RepositoryForm apiClient={apiClient} onIngestStarted={() => undefined} />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "https://gitlab.com/owner/repo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /ingest/i }));

    expect(await screen.findByText(/github\.com/i)).toBeDefined();
    expect(apiClient.ingestRepository).not.toHaveBeenCalled();
  });

  it("submits a valid URL and notifies the parent", async () => {
    const apiClient = stubApiClient();
    const onIngestStarted = vi.fn();
    render(<RepositoryForm apiClient={apiClient} onIngestStarted={onIngestStarted} />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "https://github.com/owner/repo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /ingest/i }));

    await waitFor(() => expect(onIngestStarted).toHaveBeenCalled());
    expect(apiClient.ingestRepository).toHaveBeenCalledWith("https://github.com/owner/repo");
  });
});
