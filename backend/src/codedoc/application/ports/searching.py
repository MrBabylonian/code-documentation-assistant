from dataclasses import dataclass
from typing import Protocol

from codedoc.domain.chunk import CodeChunk


@dataclass(frozen=True)
class ChunkSearchHit:
    chunk: CodeChunk
    score: float


@dataclass(frozen=True)
class FileSpan:
    file_path: str
    start_line: int  # 1-based inclusive
    end_line: int
    content: str


class ChunkSearcher(Protocol):
    async def search(
        self, repository_id: str, query_text: str, query_embedding: list[float], top_k: int
    ) -> list[ChunkSearchHit]: ...
    async def find_by_symbol(self, repository_id: str, symbol_name: str) -> list[CodeChunk]: ...


class FileContentReader(Protocol):
    async def read_span(
        self, repository_id: str, file_path: str, start_line: int, end_line: int
    ) -> FileSpan | None: ...
    async def list_paths(self, repository_id: str, path_prefix: str | None) -> list[str]: ...
