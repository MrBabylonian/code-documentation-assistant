from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from codedoc.domain.chunk import CodeChunk
from codedoc.domain.source_file import SourceFile


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk: CodeChunk
    embedding: list[float]


class ChunkIndexWriter(Protocol):
    async def write_chunks(self, embedded_chunks: Sequence[EmbeddedChunk]) -> None: ...
    async def delete_repository_chunks(self, repository_id: str) -> None: ...


class FileContentWriter(Protocol):
    async def write_files(self, repository_id: str, source_files: Sequence[SourceFile]) -> None: ...
    async def delete_repository_files(self, repository_id: str) -> None: ...
