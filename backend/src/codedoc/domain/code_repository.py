import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class IngestionStatus(StrEnum):
    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


def build_repository_id(github_url: str) -> str:
    normalized_url = github_url.strip().rstrip("/").removesuffix(".git").lower()
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:12]


@dataclass
class CodeRepository:
    repository_id: str
    github_url: str
    name: str  # "owner/repo"
    status: IngestionStatus
    error_message: str | None
    indexed_file_count: int
    indexed_chunk_count: int
    created_at: datetime  # timezone-aware UTC
    updated_at: datetime
