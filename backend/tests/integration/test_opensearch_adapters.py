import uuid
from datetime import UTC, datetime

import pytest
from opensearchpy import AsyncOpenSearch

from codedoc.application.ports.indexing import EmbeddedChunk
from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.code_repository import CodeRepository, IngestionStatus
from codedoc.domain.source_file import SourceFile
from codedoc.infrastructure.opensearch.index_bootstrapper import IndexBootstrapper
from codedoc.infrastructure.opensearch.opensearch_chunk_repository import (
    OpensearchChunkRepository,
)
from codedoc.infrastructure.opensearch.opensearch_file_store import OpensearchFileStore
from codedoc.infrastructure.opensearch.opensearch_repository_store import (
    OpensearchRepositoryStore,
)
from tests.integration.conftest import EMBEDDING_DIMENSIONS_FOR_TESTS
from tests.unit.fakes import DeterministicEmbeddings

pytestmark = pytest.mark.integration


def _new_repository_id() -> str:
    return uuid.uuid4().hex[:12]


def _make_chunk(repository_id: str, file_path: str, symbol_name: str, code: str) -> CodeChunk:
    return CodeChunk(
        chunk_id=build_chunk_id(repository_id, file_path, 1, 3),
        repository_id=repository_id,
        file_path=file_path,
        language="python",
        start_line=1,
        end_line=3,
        symbol_name=symbol_name,
        symbol_kind=SymbolKind.FUNCTION,
        enclosing_scope=None,
        docstring=None,
        code=code,
    )


async def _seed(
    chunk_repository: OpensearchChunkRepository,
    embeddings: DeterministicEmbeddings,
    repository_id: str,
    definitions: list[tuple[str, str, str]],
) -> None:
    embedded_chunks = [
        EmbeddedChunk(
            chunk=_make_chunk(repository_id, file_path, symbol_name, code),
            embedding=embeddings.embed_query(code),
        )
        for file_path, symbol_name, code in definitions
    ]
    await chunk_repository.write_chunks(embedded_chunks)


async def test_bootstrap_is_idempotent(opensearch_client: AsyncOpenSearch) -> None:
    bootstrapper = IndexBootstrapper(
        opensearch_client,
        embedding_dimensions=EMBEDDING_DIMENSIONS_FOR_TESTS,
        bm25_weight=0.3,
        knn_weight=0.7,
    )
    await bootstrapper.bootstrap()
    await bootstrapper.bootstrap()  # second run must not raise


async def test_hybrid_search_returns_relevant_chunk_first(
    bootstrapped_client: AsyncOpenSearch,
) -> None:
    repository_id = _new_repository_id()
    embeddings = DeterministicEmbeddings(dimension=EMBEDDING_DIMENSIONS_FOR_TESTS)
    chunk_repository = OpensearchChunkRepository(bootstrapped_client)
    await _seed(
        chunk_repository,
        embeddings,
        repository_id,
        [
            (
                "src/auth.py",
                "authenticate_user",
                "def authenticate_user(): validate_password_hash()",
            ),
            ("src/billing.py", "charge_card", "def charge_card(): submit_payment()"),
            ("src/report.py", "render_report", "def render_report(): build_table()"),
        ],
    )

    query_text = "def authenticate_user(): validate_password_hash()"
    hits = await chunk_repository.search(
        repository_id,
        "authenticate user password",
        embeddings.embed_query(query_text),
        top_k=3,
    )

    assert hits, "hybrid search returned nothing"
    assert hits[0].chunk.symbol_name == "authenticate_user"
    assert hits[0].score >= hits[-1].score


async def test_search_isolates_repositories(bootstrapped_client: AsyncOpenSearch) -> None:
    first_repository_id, second_repository_id = _new_repository_id(), _new_repository_id()
    embeddings = DeterministicEmbeddings(dimension=EMBEDDING_DIMENSIONS_FOR_TESTS)
    chunk_repository = OpensearchChunkRepository(bootstrapped_client)
    await _seed(
        chunk_repository,
        embeddings,
        first_repository_id,
        [("a.py", "shared_symbol", "def shared_symbol(): one()")],
    )
    await _seed(
        chunk_repository,
        embeddings,
        second_repository_id,
        [("b.py", "shared_symbol", "def shared_symbol(): two()")],
    )

    hits = await chunk_repository.search(
        first_repository_id,
        "shared_symbol",
        embeddings.embed_query("def shared_symbol(): one()"),
        top_k=10,
    )

    assert {hit.chunk.repository_id for hit in hits} == {first_repository_id}


async def test_find_by_symbol_and_delete(bootstrapped_client: AsyncOpenSearch) -> None:
    repository_id = _new_repository_id()
    embeddings = DeterministicEmbeddings(dimension=EMBEDDING_DIMENSIONS_FOR_TESTS)
    chunk_repository = OpensearchChunkRepository(bootstrapped_client)
    await _seed(
        chunk_repository,
        embeddings,
        repository_id,
        [("src/auth.py", "authenticate_user", "def authenticate_user(): pass")],
    )

    found_chunks = await chunk_repository.find_by_symbol(repository_id, "authenticate_user")
    assert [chunk.symbol_name for chunk in found_chunks] == ["authenticate_user"]
    assert found_chunks[0].code == "def authenticate_user(): pass"

    await chunk_repository.delete_repository_chunks(repository_id)
    assert await chunk_repository.find_by_symbol(repository_id, "authenticate_user") == []


async def test_file_store_roundtrip_span_and_paths(bootstrapped_client: AsyncOpenSearch) -> None:
    repository_id = _new_repository_id()
    file_store = OpensearchFileStore(bootstrapped_client)
    await file_store.write_files(
        repository_id,
        [
            SourceFile(relative_path="src/app.py", content="l1\nl2\nl3\nl4\nl5", language="python"),
            SourceFile(relative_path="docs/readme.md", content="# title", language="markdown"),
        ],
    )

    span = await file_store.read_span(repository_id, "src/app.py", 2, 4)
    assert span is not None and span.content == "l2\nl3\nl4"
    clamped_span = await file_store.read_span(repository_id, "src/app.py", 4, 99)
    assert clamped_span is not None and clamped_span.end_line == 5
    assert await file_store.read_span(repository_id, "missing.py", 1, 2) is None
    assert await file_store.list_paths(repository_id, "src/") == ["src/app.py"]
    assert await file_store.list_paths(repository_id, None) == ["docs/readme.md", "src/app.py"]


async def test_repository_store_roundtrip_and_missing(
    bootstrapped_client: AsyncOpenSearch,
) -> None:
    repository_id = _new_repository_id()
    repository_store = OpensearchRepositoryStore(bootstrapped_client)
    assert await repository_store.get(repository_id) is None

    saved_repository = CodeRepository(
        repository_id=repository_id,
        github_url="https://github.com/owner/repo",
        name="owner/repo",
        status=IngestionStatus.READY,
        error_message=None,
        indexed_file_count=3,
        indexed_chunk_count=12,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repository_store.save(saved_repository)

    loaded_repository = await repository_store.get(repository_id)
    assert loaded_repository is not None
    assert loaded_repository.status is IngestionStatus.READY
    assert loaded_repository.indexed_chunk_count == 12
    assert any(
        entry.repository_id == repository_id for entry in await repository_store.list_all()
    )
