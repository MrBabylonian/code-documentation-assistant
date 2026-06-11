from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx

from codedoc.application.answering.question_answering_service import QuestionAnsweringService
from codedoc.application.guardrails.question_scope_guard import QuestionScopeGuard
from codedoc.domain.answer import Answer, Citation
from codedoc.domain.chat import AnswerMode
from codedoc.domain.code_repository import CodeRepository, IngestionStatus
from codedoc.domain.source_file import SourceFile
from codedoc.domain.streaming import (
    AnswerCompletedEvent,
    AnswerTokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from codedoc.main import ApplicationContainer, create_application
from codedoc.settings import AppSettings
from tests.unit.fakes import (
    InMemoryFileStore,
    InMemoryRepositoryStore,
    RecordingQueryTraceWriter,
)


class StubAnswerStrategy:
    async def answer_stream(self, repository_id, question, history):  # type: ignore[no-untyped-def]
        yield ToolCallEvent(tool_name="search_code", arguments={"query": question})
        yield ToolResultEvent(tool_name="search_code", summary="<evidence …>")
        yield AnswerTokenEvent(text="It is ")
        yield AnswerCompletedEvent(answer=Answer(
            text="It is `authenticate_user`.",
            citations=[Citation(file_path="src/auth.py", start_line=1, end_line=2)],
            is_grounded=True, mode=AnswerMode.AGENTIC, model_name="stub",
            input_tokens=10, output_tokens=5, estimated_cost_usd=0.0001, latency_ms=7,
        ))


@asynccontextmanager
async def build_question_api_client():
    repository_store = InMemoryRepositoryStore()
    file_store = InMemoryFileStore()
    stub_strategy = StubAnswerStrategy()

    def container_factory(settings: AppSettings) -> ApplicationContainer:
        return ApplicationContainer(
            settings=settings,
            opensearch_client=None,
            index_bootstrapper=None,
            repository_store=repository_store,
            repository_ingestion_service=None,  # not exercised by these tests
            file_content_reader=file_store,
            question_answering_service=QuestionAnsweringService(
                repository_store=repository_store,
                scope_guard=QuestionScopeGuard(max_question_length_chars=2000),
                strategies={
                    AnswerMode.AGENTIC: stub_strategy, AnswerMode.SINGLE_SHOT: stub_strategy,
                },
                trace_writer=RecordingQueryTraceWriter(),
            ),
        )

    application = create_application(
        settings=AppSettings(openai_api_key="test-key", _env_file=None),
        container_factory=container_factory,
    )
    transport = httpx.ASGITransport(app=application)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
        application.router.lifespan_context(application),
    ):
        await repository_store.save(CodeRepository(
            repository_id="repo1", github_url="https://github.com/owner/repo",
            name="owner/repo", status=IngestionStatus.READY, error_message=None,
            indexed_file_count=1, indexed_chunk_count=1,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await file_store.write_files(
            "repo1",
            [SourceFile(relative_path="src/auth.py", content="l1\nl2\nl3", language="python")],
        )
        yield client
