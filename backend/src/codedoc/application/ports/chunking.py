from typing import Protocol

from codedoc.domain.chunk import CodeChunk
from codedoc.domain.source_file import SourceFile


class ChunkingStrategy(Protocol):
    def chunk(self, repository_id: str, source_file: SourceFile) -> list[CodeChunk]: ...
