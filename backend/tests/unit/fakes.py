import hashlib
from collections.abc import Sequence

from langchain_core.embeddings import Embeddings

from codedoc.application.ports.indexing import EmbeddedChunk
from codedoc.application.ports.searching import ChunkSearchHit, FileSpan
from codedoc.domain.chunk import CodeChunk
from codedoc.domain.code_repository import CodeRepository
from codedoc.domain.query_trace import QueryTrace
from codedoc.domain.source_file import SourceFile


class InMemoryChunkStore:
    """Implements ChunkIndexWriter + ChunkSearcher with naive term-count scoring."""

    def __init__(self) -> None:
        self._chunks_by_id: dict[str, EmbeddedChunk] = {}

    async def write_chunks(self, embedded_chunks: Sequence[EmbeddedChunk]) -> None:
        for embedded_chunk in embedded_chunks:
            self._chunks_by_id[embedded_chunk.chunk.chunk_id] = embedded_chunk

    async def delete_repository_chunks(self, repository_id: str) -> None:
        self._chunks_by_id = {
            chunk_id: embedded_chunk
            for chunk_id, embedded_chunk in self._chunks_by_id.items()
            if embedded_chunk.chunk.repository_id != repository_id
        }

    async def search(
        self, repository_id: str, query_text: str, query_embedding: list[float], top_k: int
    ) -> list[ChunkSearchHit]:
        query_terms = query_text.lower().split()
        scored_hits: list[ChunkSearchHit] = []
        for embedded_chunk in self._chunks_by_id.values():
            chunk = embedded_chunk.chunk
            if chunk.repository_id != repository_id:
                continue
            haystack = f"{chunk.code} {chunk.symbol_name or ''} {chunk.file_path}".lower()
            score = float(sum(haystack.count(term) for term in query_terms))
            if score > 0:
                scored_hits.append(ChunkSearchHit(chunk=chunk, score=score))
        scored_hits.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        return scored_hits[:top_k]

    async def find_by_symbol(self, repository_id: str, symbol_name: str) -> list[CodeChunk]:
        return [
            embedded_chunk.chunk
            for embedded_chunk in self._chunks_by_id.values()
            if embedded_chunk.chunk.repository_id == repository_id
            and embedded_chunk.chunk.symbol_name == symbol_name
        ]


class InMemoryFileStore:
    """Implements FileContentWriter + FileContentReader."""

    def __init__(self) -> None:
        self._content_by_key: dict[tuple[str, str], str] = {}

    async def write_files(self, repository_id: str, source_files: Sequence[SourceFile]) -> None:
        for source_file in source_files:
            self._content_by_key[(repository_id, source_file.relative_path)] = source_file.content

    async def delete_repository_files(self, repository_id: str) -> None:
        self._content_by_key = {
            key: content for key, content in self._content_by_key.items() if key[0] != repository_id
        }

    async def read_span(
        self, repository_id: str, file_path: str, start_line: int, end_line: int
    ) -> FileSpan | None:
        content = self._content_by_key.get((repository_id, file_path))
        if content is None:
            return None
        content_lines = content.splitlines()
        clamped_start = max(1, start_line)
        clamped_end = min(len(content_lines), end_line)
        return FileSpan(
            file_path=file_path,
            start_line=clamped_start,
            end_line=clamped_end,
            content="\n".join(content_lines[clamped_start - 1 : clamped_end]),
        )

    async def list_paths(self, repository_id: str, path_prefix: str | None) -> list[str]:
        return sorted(
            file_path
            for (stored_repository_id, file_path) in self._content_by_key
            if stored_repository_id == repository_id
            and (path_prefix is None or file_path.startswith(path_prefix))
        )


class InMemoryRepositoryStore:
    def __init__(self) -> None:
        self._repositories_by_id: dict[str, CodeRepository] = {}

    async def save(self, repository: CodeRepository) -> None:
        self._repositories_by_id[repository.repository_id] = repository

    async def get(self, repository_id: str) -> CodeRepository | None:
        return self._repositories_by_id.get(repository_id)

    async def list_all(self) -> list[CodeRepository]:
        return list(self._repositories_by_id.values())


class RecordingQueryTraceWriter:
    def __init__(self) -> None:
        self.recorded_traces: list[QueryTrace] = []

    async def write_trace(self, trace: QueryTrace) -> None:
        self.recorded_traces.append(trace)


class DeterministicEmbeddings(Embeddings):
    """Hash-derived fixed-dimension vectors — stable, fast, never calls a network."""

    def __init__(self, dimension: int = 32) -> None:
        self._dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.md5(text.encode("utf-8")).digest()
        return [digest[index % len(digest)] / 255.0 for index in range(self._dimension)]
