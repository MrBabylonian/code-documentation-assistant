import tempfile
from datetime import UTC, datetime
from pathlib import Path

import structlog
from langchain_core.embeddings import Embeddings

from codedoc.application.ingestion.chunking.chunking_strategy_resolver import (
    ChunkingStrategyResolver,
)
from codedoc.application.ingestion.source_file_scanner import SourceFileScanner
from codedoc.application.ports.cloning import RepositoryCloneClient
from codedoc.application.ports.indexing import ChunkIndexWriter, EmbeddedChunk, FileContentWriter
from codedoc.application.ports.repository_store import RepositoryStore
from codedoc.domain.chunk import CodeChunk
from codedoc.domain.code_repository import CodeRepository, IngestionStatus, build_repository_id
from codedoc.domain.source_file import SourceFile

logger = structlog.get_logger()


class RepositoryIngestionService:
    """Clones, scans, chunks, embeds, and indexes one repository; tracks status per stage."""

    def __init__(
        self,
        clone_client: RepositoryCloneClient,
        source_file_scanner: SourceFileScanner,
        chunking_strategy_resolver: ChunkingStrategyResolver,
        embeddings: Embeddings,
        chunk_index_writer: ChunkIndexWriter,
        file_content_writer: FileContentWriter,
        repository_store: RepositoryStore,
        embedding_batch_size: int,
    ) -> None:
        self._clone_client = clone_client
        self._source_file_scanner = source_file_scanner
        self._chunking_strategy_resolver = chunking_strategy_resolver
        self._embeddings = embeddings
        self._chunk_index_writer = chunk_index_writer
        self._file_content_writer = file_content_writer
        self._repository_store = repository_store
        self._embedding_batch_size = embedding_batch_size

    async def ingest(self, github_url: str) -> str:
        repository_id = build_repository_id(github_url)
        repository = CodeRepository(
            repository_id=repository_id,
            github_url=github_url,
            name=github_url.removesuffix("/").removesuffix(".git").split("github.com/")[-1],
            status=IngestionStatus.PENDING,
            error_message=None,
            indexed_file_count=0,
            indexed_chunk_count=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await self._save(repository)
        try:
            await self._run_pipeline(repository)
        except Exception as ingestion_error:  # noqa: BLE001
            # boundary silencing: this runs as a fire-and-forget background task; an exception
            # must land in the status document (and the log), never crash the event loop task
            repository.status = IngestionStatus.FAILED
            repository.error_message = str(ingestion_error)
            await self._save(repository)
            logger.error("ingestion_failed", repository_id=repository.repository_id,
                         error=str(ingestion_error))
        return repository_id

    async def _run_pipeline(self, repository: CodeRepository) -> None:
        with tempfile.TemporaryDirectory(prefix="codedoc-clone-") as temporary_directory_name:
            repository.status = IngestionStatus.CLONING
            await self._save(repository)
            cloned_repository = await self._clone_client.clone(
                repository.github_url, Path(temporary_directory_name) / "clone"
            )
            repository.name = cloned_repository.name

            repository.status = IngestionStatus.PARSING
            await self._save(repository)
            source_files = self._source_file_scanner.scan(cloned_repository.clone_path)
            chunks = self._chunk_all(repository.repository_id, source_files)

            repository.status = IngestionStatus.EMBEDDING
            await self._save(repository)
            embedded_chunks = await self._embed_in_batches(chunks)

            repository.status = IngestionStatus.INDEXING
            await self._save(repository)
            await self._chunk_index_writer.delete_repository_chunks(repository.repository_id)
            await self._file_content_writer.delete_repository_files(repository.repository_id)
            await self._chunk_index_writer.write_chunks(embedded_chunks)
            await self._file_content_writer.write_files(repository.repository_id, source_files)

            repository.status = IngestionStatus.READY
            repository.indexed_file_count = len(source_files)
            repository.indexed_chunk_count = len(embedded_chunks)
            await self._save(repository)
            logger.info("ingestion_completed", repository_id=repository.repository_id,
                        file_count=len(source_files), chunk_count=len(embedded_chunks))

    def _chunk_all(self, repository_id: str, source_files: list[SourceFile]) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        for source_file in source_files:
            strategy = self._chunking_strategy_resolver.resolve(source_file.language)
            chunks.extend(strategy.chunk(repository_id, source_file))
        return chunks

    async def _embed_in_batches(self, chunks: list[CodeChunk]) -> list[EmbeddedChunk]:
        embedded_chunks: list[EmbeddedChunk] = []
        for batch_start in range(0, len(chunks), self._embedding_batch_size):
            chunk_batch = chunks[batch_start : batch_start + self._embedding_batch_size]
            vectors = await self._embeddings.aembed_documents(
                [chunk.composed_embedding_text for chunk in chunk_batch]
            )
            embedded_chunks.extend(
                EmbeddedChunk(chunk=chunk, embedding=vector)
                for chunk, vector in zip(chunk_batch, vectors, strict=True)
            )
        return embedded_chunks

    async def _save(self, repository: CodeRepository) -> None:
        repository.updated_at = datetime.now(UTC)
        await self._repository_store.save(repository)
