import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/lib/apiClient";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ApiClient", () => {
  it("posts an ingest request and returns the repository id", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ repository_id: "abc123def456" }, 202));
    const apiClient = new ApiClient("http://api.test");

    const ingestResult = await apiClient.ingestRepository("https://github.com/owner/repo");

    expect(ingestResult.repository_id).toBe("abc123def456");
    const [requestUrl, requestInit] = fetchSpy.mock.calls[0];
    expect(requestUrl).toBe("http://api.test/api/repositories");
    expect(requestInit?.method).toBe("POST");
  });

  it("returns null for a 404 repository and throws on server errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("not found", { status: 404 }));
    const apiClient = new ApiClient("http://api.test");
    expect(await apiClient.getRepository("missing")).toBeNull();

    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("boom", { status: 500 }));
    await expect(apiClient.listRepositories()).rejects.toThrowError(/500/);
  });

  it("streamAnswer returns the raw Response for SSE reading", async () => {
    const sseResponse = new Response("data: {}\n\n", { status: 200 });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(sseResponse);
    const apiClient = new ApiClient("http://api.test");

    const streamResponse = await apiClient.streamAnswer("abc", "where?", "agentic", []);

    expect(streamResponse).toBe(sseResponse);
  });
});
