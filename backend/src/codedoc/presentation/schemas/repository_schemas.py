import re
from datetime import datetime

from pydantic import BaseModel, field_validator

from codedoc.domain.code_repository import CodeRepository

GITHUB_URL_PATTERN = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+(\.git)?/?$")


class IngestRepositoryRequest(BaseModel):
    github_url: str

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, github_url: str) -> str:
        if GITHUB_URL_PATTERN.match(github_url.strip()) is None:
            raise ValueError("must be a public github.com repository URL")
        return github_url.strip()


class IngestRepositoryResponse(BaseModel):
    repository_id: str


class RepositoryResponse(BaseModel):
    repository_id: str
    github_url: str
    name: str
    status: str
    error_message: str | None
    indexed_file_count: int
    indexed_chunk_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, repository: CodeRepository) -> "RepositoryResponse":
        return cls(
            repository_id=repository.repository_id,
            github_url=repository.github_url,
            name=repository.name,
            status=repository.status.value,
            error_message=repository.error_message,
            indexed_file_count=repository.indexed_file_count,
            indexed_chunk_count=repository.indexed_chunk_count,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
        )
