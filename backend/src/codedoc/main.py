import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from fastapi import FastAPI, Request, Response
from opensearchpy import AsyncOpenSearch

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
from codedoc.application.ports.repository_store import RepositoryStore
from codedoc.infrastructure.git.git_clone_client import GitCloneClient
from codedoc.infrastructure.opensearch.index_bootstrapper import IndexBootstrapper
from codedoc.infrastructure.opensearch.opensearch_chunk_repository import (
    OpensearchChunkRepository,
)
from codedoc.infrastructure.opensearch.opensearch_file_store import OpensearchFileStore
from codedoc.infrastructure.opensearch.opensearch_repository_store import (
    OpensearchRepositoryStore,
)
from codedoc.presentation.routers.repository_router import repository_router
from codedoc.settings import AppSettings
from codedoc.structured_logging import configure_logging


@dataclass
class ApplicationContainer:
    settings: AppSettings
    opensearch_client: AsyncOpenSearch | None
    index_bootstrapper: IndexBootstrapper | None
    repository_store: RepositoryStore
    repository_ingestion_service: RepositoryIngestionService
    # Task 18 adds: question_answering_service, file_content_reader


def _build_default_container(settings: AppSettings) -> ApplicationContainer:
    from langchain_openai import OpenAIEmbeddings

    opensearch_client = AsyncOpenSearch(hosts=[settings.opensearch_url])
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model_name, openai_api_key=settings.openai_api_key
    )
    repository_store = OpensearchRepositoryStore(opensearch_client)
    chunk_repository = OpensearchChunkRepository(opensearch_client)
    file_store = OpensearchFileStore(opensearch_client)
    return ApplicationContainer(
        settings=settings,
        opensearch_client=opensearch_client,
        index_bootstrapper=IndexBootstrapper(
            opensearch_client,
            embedding_dimensions=settings.embedding_dimensions,
            bm25_weight=settings.bm25_weight,
            knn_weight=settings.knn_weight,
        ),
        repository_store=repository_store,
        repository_ingestion_service=RepositoryIngestionService(
            clone_client=GitCloneClient(
                clone_timeout_seconds=settings.clone_timeout_seconds,
                max_repository_size_mb=settings.max_repository_size_mb,
            ),
            source_file_scanner=SourceFileScanner(max_file_size_kb=settings.max_file_size_kb),
            chunking_strategy_resolver=ChunkingStrategyResolver(
                tree_sitter_strategy=TreeSitterChunkingStrategy(),
                line_window_strategy=LineWindowChunkingStrategy(),
            ),
            embeddings=embeddings,
            chunk_index_writer=chunk_repository,
            file_content_writer=file_store,
            repository_store=repository_store,
            embedding_batch_size=settings.embedding_batch_size,
        ),
    )


def create_application(
    settings: AppSettings | None = None,
    container_factory: Callable[[AppSettings], ApplicationContainer] | None = None,
) -> FastAPI:
    configure_logging()
    resolved_settings = settings if settings is not None else AppSettings()
    build_container = (
        container_factory if container_factory is not None else _build_default_container
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        container = build_container(resolved_settings)
        application.state.container = container
        application.state.ingestion_tasks = set()
        if container.index_bootstrapper is not None:
            await container.index_bootstrapper.bootstrap()
        yield
        if container.opensearch_client is not None:
            await container.opensearch_client.close()

    application = FastAPI(title="codedoc", lifespan=lifespan)

    @application.middleware("http")
    async def bind_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(repository_router)
    return application
