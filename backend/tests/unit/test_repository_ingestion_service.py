from pathlib import Path

from codedoc.application.ingestion.chunking.chunking_strategy_resolver import (
    ChunkingStrategyResolver,
)
from codedoc.application.ingestion.chunking.line_window_chunking_strategy import (
    LineWindowChunkingStrategy,
)
from codedoc.application.ingestion.chunking.tree_sitter_chunking_strategy import (
    TreeSitterChunkingStrategy,
)
from codedoc.application.ingestion.repository_ingestion_service import (
    RepositoryIngestionService,
)
from codedoc.application.ingestion.source_file_scanner import SourceFileScanner
from codedoc.application.ports.cloning import ClonedRepository
from codedoc.domain.code_repository import IngestionStatus, build_repository_id
from codedoc.domain.errors import CloneError
from tests.unit.fakes import (
    DeterministicEmbeddings,
    InMemoryChunkStore,
    InMemoryFileStore,
    InMemoryRepositoryStore,
)

FIXTURE_FILES = {
    "src/app.py": "def main():\n    return 1\n",
    "README.md": "# Fixture\n",
}


class FakeCloneClient:
    """Writes fixture files into the destination instead of running git."""

    def __init__(self, files: dict[str, str], failure: Exception | None = None) -> None:
        self._files = files
        self._failure = failure

    async def clone(self, github_url: str, destination: Path) -> ClonedRepository:
        if self._failure is not None:
            raise self._failure
        for relative_path, content in self._files.items():
            target_path = destination / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
        return ClonedRepository(name="owner/fixture", clone_path=destination)


class StatusRecordingRepositoryStore(InMemoryRepositoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.recorded_statuses: list[IngestionStatus] = []

    async def save(self, repository) -> None:  # type: ignore[no-untyped-def]
        self.recorded_statuses.append(repository.status)
        await super().save(repository)


class BatchRecordingEmbeddings(DeterministicEmbeddings):
    def __init__(self, dimension: int = 8) -> None:
        super().__init__(dimension=dimension)
        self.recorded_batch_sizes: list[int] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.recorded_batch_sizes.append(len(texts))
        return await super().aembed_documents(texts)


def _build_service(
    clone_client: FakeCloneClient,
    repository_store: StatusRecordingRepositoryStore,
    chunk_store: InMemoryChunkStore,
    file_store: InMemoryFileStore,
    embeddings: BatchRecordingEmbeddings,
    embedding_batch_size: int = 64,
) -> RepositoryIngestionService:
    tree_sitter_strategy = TreeSitterChunkingStrategy()
    return RepositoryIngestionService(
        clone_client=clone_client,
        source_file_scanner=SourceFileScanner(max_file_size_kb=512),
        chunking_strategy_resolver=ChunkingStrategyResolver(
            tree_sitter_strategy=tree_sitter_strategy,
            line_window_strategy=LineWindowChunkingStrategy(),
        ),
        embeddings=embeddings,
        chunk_index_writer=chunk_store,
        file_content_writer=file_store,
        repository_store=repository_store,
        embedding_batch_size=embedding_batch_size,
    )


async def test_happy_path_walks_the_full_status_lifecycle_and_indexes() -> None:
    repository_store = StatusRecordingRepositoryStore()
    chunk_store = InMemoryChunkStore()
    file_store = InMemoryFileStore()
    service = _build_service(
        FakeCloneClient(FIXTURE_FILES), repository_store, chunk_store, file_store,
        BatchRecordingEmbeddings(),
    )

    repository_id = await service.ingest("https://github.com/owner/fixture")

    assert repository_id == build_repository_id("https://github.com/owner/fixture")
    assert repository_store.recorded_statuses == [
        IngestionStatus.PENDING, IngestionStatus.CLONING, IngestionStatus.PARSING,
        IngestionStatus.EMBEDDING, IngestionStatus.INDEXING, IngestionStatus.READY,
    ]
    stored_repository = await repository_store.get(repository_id)
    assert stored_repository is not None
    assert stored_repository.name == "owner/fixture"
    assert stored_repository.indexed_file_count == 2
    assert stored_repository.indexed_chunk_count > 0
    assert await chunk_store.find_by_symbol(repository_id, "main")
    assert await file_store.read_span(repository_id, "README.md", 1, 1) is not None


async def test_clone_failure_marks_failed_with_message_and_does_not_raise() -> None:
    repository_store = StatusRecordingRepositoryStore()
    service = _build_service(
        FakeCloneClient(FIXTURE_FILES, failure=CloneError("clone timed out after 120s")),
        repository_store, InMemoryChunkStore(), InMemoryFileStore(), BatchRecordingEmbeddings(),
    )

    repository_id = await service.ingest("https://github.com/owner/fixture")

    stored_repository = await repository_store.get(repository_id)
    assert stored_repository is not None
    assert stored_repository.status is IngestionStatus.FAILED
    assert stored_repository.error_message == "clone timed out after 120s"


async def test_re_ingestion_deletes_previous_documents_first() -> None:
    class DeleteRecordingChunkStore(InMemoryChunkStore):
        def __init__(self) -> None:
            super().__init__()
            self.delete_call_count = 0

        async def delete_repository_chunks(self, repository_id: str) -> None:
            self.delete_call_count += 1
            await super().delete_repository_chunks(repository_id)

    repository_store = StatusRecordingRepositoryStore()
    chunk_store = DeleteRecordingChunkStore()
    service = _build_service(
        FakeCloneClient(FIXTURE_FILES), repository_store, chunk_store,
        InMemoryFileStore(), BatchRecordingEmbeddings(),
    )

    await service.ingest("https://github.com/owner/fixture")
    await service.ingest("https://github.com/owner/fixture")

    assert chunk_store.delete_call_count == 2  # delete-then-write on every run → idempotent


async def test_embedding_runs_in_configured_batches() -> None:
    many_files = {f"src/module_{index}.py": "def handler():\n    return 1\n" for index in range(5)}
    embeddings = BatchRecordingEmbeddings()
    service = _build_service(
        FakeCloneClient(many_files), StatusRecordingRepositoryStore(), InMemoryChunkStore(),
        InMemoryFileStore(), embeddings, embedding_batch_size=2,
    )

    await service.ingest("https://github.com/owner/fixture")

    assert all(batch_size <= 2 for batch_size in embeddings.recorded_batch_sizes)
    assert sum(embeddings.recorded_batch_sizes) >= 5
