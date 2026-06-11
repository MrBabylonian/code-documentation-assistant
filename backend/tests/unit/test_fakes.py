from codedoc.application.ports.indexing import EmbeddedChunk
from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.source_file import SourceFile
from tests.unit.fakes import (
    DeterministicEmbeddings,
    InMemoryChunkStore,
    InMemoryFileStore,
    InMemoryRepositoryStore,
)


def _make_chunk(repository_id: str, file_path: str, symbol_name: str, code: str) -> CodeChunk:
    return CodeChunk(
        chunk_id=build_chunk_id(repository_id, file_path, 1, 5),
        repository_id=repository_id, file_path=file_path, language="python",
        start_line=1, end_line=5, symbol_name=symbol_name,
        symbol_kind=SymbolKind.FUNCTION, enclosing_scope=None, docstring=None, code=code,
    )


async def test_chunk_store_search_ranks_matching_code_first() -> None:
    chunk_store = InMemoryChunkStore()
    auth_chunk = _make_chunk(
        "repo1", "src/auth.py", "authenticate_user", "def authenticate_user(): check_password()"
    )
    billing_chunk = _make_chunk(
        "repo1", "src/billing.py", "charge_card", "def charge_card(): password_required()"
    )
    await chunk_store.write_chunks(
        [
            EmbeddedChunk(chunk=auth_chunk, embedding=[0.0]),
            EmbeddedChunk(chunk=billing_chunk, embedding=[0.0]),
        ]
    )

    hits = await chunk_store.search("repo1", "authenticate password", [0.0], top_k=2)

    assert hits[0].chunk.symbol_name == "authenticate_user"
    assert hits[0].score > hits[1].score


async def test_chunk_store_isolates_repositories_and_deletes() -> None:
    chunk_store = InMemoryChunkStore()
    await chunk_store.write_chunks(
        [EmbeddedChunk(chunk=_make_chunk("repo1", "a.py", "alpha", "alpha"), embedding=[0.0])]
    )
    await chunk_store.write_chunks(
        [EmbeddedChunk(chunk=_make_chunk("repo2", "b.py", "alpha", "alpha"), embedding=[0.0])]
    )

    assert len(await chunk_store.find_by_symbol("repo1", "alpha")) == 1
    await chunk_store.delete_repository_chunks("repo1")
    assert await chunk_store.find_by_symbol("repo1", "alpha") == []
    assert len(await chunk_store.find_by_symbol("repo2", "alpha")) == 1


async def test_file_store_span_slicing_and_clamping() -> None:
    file_store = InMemoryFileStore()
    await file_store.write_files(
        "repo1",
        [SourceFile(relative_path="src/app.py", content="l1\nl2\nl3\nl4", language="python")],
    )

    span = await file_store.read_span("repo1", "src/app.py", 2, 3)
    assert span is not None and span.content == "l2\nl3"
    clamped_span = await file_store.read_span("repo1", "src/app.py", 3, 99)
    assert clamped_span is not None and clamped_span.end_line == 4
    assert await file_store.read_span("repo1", "missing.py", 1, 2) is None
    assert await file_store.read_span("repo1", "src/app.py", 10, 12) is None
    assert await file_store.list_paths("repo1", "src/") == ["src/app.py"]
    assert await file_store.list_paths("repo1", "docs/") == []


async def test_repository_store_roundtrip() -> None:
    from datetime import UTC, datetime

    from codedoc.domain.code_repository import CodeRepository, IngestionStatus

    repository_store = InMemoryRepositoryStore()
    assert await repository_store.get("missing") is None
    repository = CodeRepository(
        repository_id="abc", github_url="https://github.com/owner/repo", name="owner/repo",
        status=IngestionStatus.PENDING, error_message=None, indexed_file_count=0,
        indexed_chunk_count=0, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    await repository_store.save(repository)
    stored_repository = await repository_store.get("abc")
    assert stored_repository is not None and stored_repository.name == "owner/repo"
    assert [entry.repository_id for entry in await repository_store.list_all()] == ["abc"]


async def test_deterministic_embeddings_are_stable_and_sized() -> None:
    embeddings = DeterministicEmbeddings(dimension=32)
    first_vector = await embeddings.aembed_query("hello")
    second_vector = await embeddings.aembed_query("hello")
    other_vector = await embeddings.aembed_query("different")
    assert first_vector == second_vector
    assert len(first_vector) == 32
    assert first_vector != other_vector
    document_vectors = embeddings.embed_documents(["alpha", "beta"])
    assert len(document_vectors) == 2


def test_fakes_satisfy_their_protocols() -> None:
    from codedoc.application.ports.indexing import ChunkIndexWriter, FileContentWriter
    from codedoc.application.ports.repository_store import RepositoryStore
    from codedoc.application.ports.searching import ChunkSearcher, FileContentReader
    from codedoc.application.ports.tracing import QueryTraceWriter
    from tests.unit.fakes import RecordingQueryTraceWriter

    chunk_writer: ChunkIndexWriter = InMemoryChunkStore()
    chunk_searcher: ChunkSearcher = InMemoryChunkStore()
    file_writer: FileContentWriter = InMemoryFileStore()
    file_reader: FileContentReader = InMemoryFileStore()
    repository_store: RepositoryStore = InMemoryRepositoryStore()
    trace_writer: QueryTraceWriter = RecordingQueryTraceWriter()
    assert all(
        instance is not None
        for instance in (
            chunk_writer, chunk_searcher, file_writer, file_reader, repository_store, trace_writer
        )
    )
