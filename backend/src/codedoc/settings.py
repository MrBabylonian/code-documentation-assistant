from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODEDOC_", env_file=".env", extra="ignore")

    opensearch_url: str = "http://localhost:9200"
    openai_api_key: str

    chat_model_name: str = "gpt-5.4-mini"
    embedding_model_name: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    clone_timeout_seconds: int = 120
    max_repository_size_mb: int = 200
    max_file_size_kb: int = 512
    embedding_batch_size: int = 64

    search_top_k: int = 8
    max_tool_calls: int = 8
    max_evidence_tokens_per_result: int = 2000
    max_history_turns: int = 6
    max_question_length_chars: int = 2000

    knn_weight: float = 0.7
    bm25_weight: float = 0.3

    chat_input_cost_per_mtok_usd: float = 0.75
    chat_output_cost_per_mtok_usd: float = 4.50
