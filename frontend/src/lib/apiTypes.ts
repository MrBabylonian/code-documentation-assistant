export type IngestionStatus =
  | "pending"
  | "cloning"
  | "parsing"
  | "embedding"
  | "indexing"
  | "ready"
  | "failed";

export interface RepositoryResponse {
  repository_id: string;
  github_url: string;
  name: string;
  status: IngestionStatus;
  error_message: string | null;
  indexed_file_count: number;
  indexed_chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface CitationPayload {
  file_path: string;
  start_line: number;
  end_line: number;
}

export type AnswerMode = "agentic" | "single_shot";

export interface AnswerPayload {
  text: string;
  citations: CitationPayload[];
  is_grounded: boolean;
  mode: AnswerMode;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  latency_ms: number;
}

export interface ChatTurnPayload {
  role: "user" | "assistant";
  text: string;
}

export interface FileSpanResponse {
  file_path: string;
  start_line: number;
  end_line: number;
  content: string;
}

export type AnswerStreamEvent =
  | { kind: "tool_call"; tool_name: string; arguments: Record<string, unknown> }
  | { kind: "tool_result"; tool_name: string; summary: string }
  | { kind: "answer_token"; text: string }
  | { kind: "answer_restart"; reason: string }
  | { kind: "answer_completed"; answer: AnswerPayload }
  | { kind: "error"; message: string };
