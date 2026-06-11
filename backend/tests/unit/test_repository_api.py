import asyncio
from pathlib import Path

import httpx
import pytest

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
from codedoc.main import ApplicationContainer, create_application
from codedoc.settings import AppSettings
from tests.unit.fakes import (
    DeterministicEmbeddings,
    InMemoryChunkStore,
    InMemoryFileStore,
    InMemoryRepositoryStore,
)


class FakeCloneClient:
    async def clone(self, github_url: str, destination: Path) -> ClonedRepository:
        app_file_path = destination / "src" / "app.py"
        app_file_path.parent.mkdir(parents=True, exist_ok=True)
        app_file_path.write_text("def main():\n    return 1\n", encoding="utf-8")
        return ClonedRepository(name="owner/fixture", clone_path=destination)


def _fake_container_factory(settings: AppSettings) -> ApplicationContainer:
    repository_store = InMemoryRepositoryStore()
    return ApplicationContainer(
        settings=settings,
        opensearch_client=None,
        index_bootstrapper=None,
        repository_store=repository_store,
        repository_ingestion_service=RepositoryIngestionService(
            clone_client=FakeCloneClient(),
            source_file_scanner=SourceFileScanner(max_file_size_kb=settings.max_file_size_kb),
            chunking_strategy_resolver=ChunkingStrategyResolver(
                tree_sitter_strategy=TreeSitterChunkingStrategy(),
                line_window_strategy=LineWindowChunkingStrategy(),
            ),
            embeddings=DeterministicEmbeddings(),
            chunk_index_writer=InMemoryChunkStore(),
            file_content_writer=InMemoryFileStore(),
            repository_store=repository_store,
            embedding_batch_size=settings.embedding_batch_size,
        ),
    )


@pytest.fixture
async def api_client() -> httpx.AsyncClient:
    application = create_application(
        settings=AppSettings(openai_api_key="test-key", _env_file=None),
        container_factory=_fake_container_factory,
    )
    # httpx 0.28 removed the app= shortcut; ASGITransport is the supported in-process route
    transport = httpx.ASGITransport(app=application)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
        # ASGITransport does not run lifespan; trigger it explicitly via the router events
        application.router.lifespan_context(application),
    ):
        yield client


async def test_healthz(api_client: httpx.AsyncClient) -> None:
    health_response = await api_client.get("/healthz")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert "x-request-id" in health_response.headers


async def test_ingest_returns_202_and_reaches_ready(api_client: httpx.AsyncClient) -> None:
    ingest_response = await api_client.post(
        "/api/repositories", json={"github_url": "https://github.com/owner/fixture"}
    )
    assert ingest_response.status_code == 202
    repository_id = ingest_response.json()["repository_id"]

    async def _wait_until_ready() -> dict[str, object]:
        while True:
            status_response = await api_client.get(f"/api/repositories/{repository_id}")
            if status_response.status_code == 200 and status_response.json()["status"] in (
                "ready",
                "failed",
            ):
                return dict(status_response.json())
            await asyncio.sleep(0.01)

    repository_payload = await asyncio.wait_for(_wait_until_ready(), timeout=5)
    assert repository_payload["status"] == "ready"
    assert repository_payload["name"] == "owner/fixture"
    assert int(str(repository_payload["indexed_chunk_count"])) > 0


async def test_ingest_rejects_non_github_urls(api_client: httpx.AsyncClient) -> None:
    bad_url_response = await api_client.post(
        "/api/repositories", json={"github_url": "https://gitlab.com/owner/repo"}
    )
    assert bad_url_response.status_code == 422


async def test_get_unknown_repository_returns_404(api_client: httpx.AsyncClient) -> None:
    missing_response = await api_client.get("/api/repositories/unknown123456")
    assert missing_response.status_code == 404


async def test_list_repositories(api_client: httpx.AsyncClient) -> None:
    await api_client.post(
        "/api/repositories", json={"github_url": "https://github.com/owner/fixture"}
    )
    list_response = await api_client.get("/api/repositories")
    assert list_response.status_code == 200
    assert isinstance(list_response.json(), list)
