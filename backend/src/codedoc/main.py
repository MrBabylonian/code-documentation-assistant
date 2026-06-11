import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from fastapi import FastAPI, Request, Response
from opensearchpy import AsyncOpenSearch

from codedoc.application.answering.citation_parser import CitationParser
from codedoc.application.answering.citation_validator import CitationValidator
from codedoc.application.answering.evidence_formatter import EvidenceFormatter
from codedoc.application.answering.prompt_loader import SystemPromptLoader
from codedoc.application.answering.question_answering_service import QuestionAnsweringService
from codedoc.application.answering.single_shot_answer_strategy import SingleShotAnswerStrategy
from codedoc.application.answering.token_cost_calculator import TokenCostCalculator
from codedoc.application.guardrails.question_scope_guard import QuestionScopeGuard
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
from codedoc.application.ports.searching import FileContentReader
from codedoc.domain.chat import AnswerMode
from codedoc.infrastructure.agents.agent_toolset import AgentToolset
from codedoc.infrastructure.agents.agentic_answer_strategy import AgenticAnswerStrategy
from codedoc.infrastructure.git.git_clone_client import GitCloneClient
from codedoc.infrastructure.opensearch.index_bootstrapper import IndexBootstrapper
from codedoc.infrastructure.opensearch.opensearch_chunk_repository import (
    OpensearchChunkRepository,
)
from codedoc.infrastructure.opensearch.opensearch_file_store import OpensearchFileStore
from codedoc.infrastructure.opensearch.opensearch_query_trace_writer import (
    OpensearchQueryTraceWriter,
)
from codedoc.infrastructure.opensearch.opensearch_repository_store import (
    OpensearchRepositoryStore,
)
from codedoc.presentation.routers.question_router import question_router
from codedoc.presentation.routers.repository_router import repository_router
from codedoc.settings import AppSettings
from codedoc.structured_logging import configure_logging


@dataclass
class ApplicationContainer:
    settings: AppSettings
    opensearch_client: AsyncOpenSearch | None
    index_bootstrapper: IndexBootstrapper | None
    repository_store: RepositoryStore
    repository_ingestion_service: RepositoryIngestionService | None
    file_content_reader: FileContentReader | None
    question_answering_service: QuestionAnsweringService | None


def _build_default_container(settings: AppSettings) -> ApplicationContainer:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    opensearch_client = AsyncOpenSearch(hosts=[settings.opensearch_url])
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model_name, openai_api_key=settings.openai_api_key
    )
    repository_store = OpensearchRepositoryStore(opensearch_client)
    chunk_repository = OpensearchChunkRepository(opensearch_client)
    file_store = OpensearchFileStore(opensearch_client)
    chat_model = ChatOpenAI(
        model=settings.chat_model_name,
        # field name, not the "api_key" alias: mypy strict + pydantic plugin reject alias kwargs
        openai_api_key=settings.openai_api_key,
        # OpenAI does not stream usage by default; without this flag token counts are zero
        stream_usage=True,
    )
    evidence_formatter = EvidenceFormatter(
        max_evidence_tokens_per_result=settings.max_evidence_tokens_per_result
    )
    citation_parser = CitationParser()
    citation_validator = CitationValidator()
    prompt_loader = SystemPromptLoader()
    token_cost_calculator = TokenCostCalculator(
        input_cost_per_mtok_usd=settings.chat_input_cost_per_mtok_usd,
        output_cost_per_mtok_usd=settings.chat_output_cost_per_mtok_usd,
    )

    def toolset_factory(repository_id: str) -> AgentToolset:
        return AgentToolset(
            repository_id=repository_id,
            chunk_searcher=chunk_repository,
            file_content_reader=file_store,
            embeddings=embeddings,
            evidence_formatter=evidence_formatter,
            search_top_k=settings.search_top_k,
        )

    question_answering_service = QuestionAnsweringService(
        repository_store=repository_store,
        scope_guard=QuestionScopeGuard(
            max_question_length_chars=settings.max_question_length_chars
        ),
        strategies={
            AnswerMode.AGENTIC: AgenticAnswerStrategy(
                chat_model=chat_model,
                toolset_factory=toolset_factory,
                citation_parser=citation_parser,
                citation_validator=citation_validator,
                prompt_loader=prompt_loader,
                token_cost_calculator=token_cost_calculator,
                max_tool_calls=settings.max_tool_calls,
                max_history_turns=settings.max_history_turns,
                model_name=settings.chat_model_name,
            ),
            AnswerMode.SINGLE_SHOT: SingleShotAnswerStrategy(
                chat_model=chat_model,
                embeddings=embeddings,
                chunk_searcher=chunk_repository,
                evidence_formatter=evidence_formatter,
                citation_parser=citation_parser,
                citation_validator=citation_validator,
                prompt_loader=prompt_loader,
                token_cost_calculator=token_cost_calculator,
                search_top_k=settings.search_top_k,
                max_history_turns=settings.max_history_turns,
                model_name=settings.chat_model_name,
            ),
        },
        trace_writer=OpensearchQueryTraceWriter(opensearch_client),
    )
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
        file_content_reader=file_store,
        question_answering_service=question_answering_service,
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
    application.include_router(question_router)
    return application
