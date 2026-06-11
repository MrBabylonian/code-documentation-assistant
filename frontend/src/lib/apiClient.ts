import type {
  AnswerMode,
  ChatTurnPayload,
  FileSpanResponse,
  RepositoryResponse,
} from "@/lib/apiTypes";

export class ApiClient {
  #baseUrl: string;

  constructor(baseUrl: string) {
    this.#baseUrl = baseUrl.replace(/\/$/, "");
  }

  async ingestRepository(githubUrl: string): Promise<{ repository_id: string }> {
    const response = await fetch(`${this.#baseUrl}/api/repositories`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ github_url: githubUrl }),
    });
    await this.#assertOk(response);
    return (await response.json()) as { repository_id: string };
  }

  async listRepositories(): Promise<RepositoryResponse[]> {
    const response = await fetch(`${this.#baseUrl}/api/repositories`);
    await this.#assertOk(response);
    return (await response.json()) as RepositoryResponse[];
  }

  async getRepository(repositoryId: string): Promise<RepositoryResponse | null> {
    const response = await fetch(`${this.#baseUrl}/api/repositories/${repositoryId}`);
    if (response.status === 404) return null;
    await this.#assertOk(response);
    return (await response.json()) as RepositoryResponse;
  }

  async fetchFileSpan(
    repositoryId: string,
    filePath: string,
    startLine: number,
    endLine: number,
  ): Promise<FileSpanResponse | null> {
    const queryParameters = new URLSearchParams({
      file_path: filePath,
      start_line: String(startLine),
      end_line: String(endLine),
    });
    const response = await fetch(
      `${this.#baseUrl}/api/repositories/${repositoryId}/file-spans?${queryParameters}`,
    );
    if (response.status === 404) return null;
    await this.#assertOk(response);
    return (await response.json()) as FileSpanResponse;
  }

  async streamAnswer(
    repositoryId: string,
    question: string,
    mode: AnswerMode,
    history: ChatTurnPayload[],
  ): Promise<Response> {
    const response = await fetch(`${this.#baseUrl}/api/repositories/${repositoryId}/answers`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, mode, history }),
    });
    await this.#assertOk(response);
    return response;
  }

  async #assertOk(response: Response): Promise<void> {
    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(`API request failed (${response.status}): ${errorBody}`);
    }
  }
}
