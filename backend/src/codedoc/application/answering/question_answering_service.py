import json
import time
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import structlog

from codedoc.application.guardrails.question_scope_guard import QuestionScopeGuard
from codedoc.application.ports.answering import AnswerStrategy
from codedoc.application.ports.repository_store import RepositoryStore
from codedoc.application.ports.tracing import QueryTraceWriter
from codedoc.domain.answer import Answer
from codedoc.domain.chat import AnswerMode, ChatTurn
from codedoc.domain.code_repository import IngestionStatus
from codedoc.domain.query_trace import QueryTrace, TraceStep
from codedoc.domain.streaming import (
    AnswerCompletedEvent,
    AnswerRestartEvent,
    AnswerStreamEvent,
    ErrorEvent,
    ToolCallEvent,
    ToolResultEvent,
)

logger = structlog.get_logger()


class QuestionAnsweringService:
    """Gate (scope, readiness) → delegate to the selected strategy → record a trace."""

    def __init__(
        self,
        repository_store: RepositoryStore,
        scope_guard: QuestionScopeGuard,
        strategies: Mapping[AnswerMode, AnswerStrategy],
        trace_writer: QueryTraceWriter,
    ) -> None:
        self._repository_store = repository_store
        self._scope_guard = scope_guard
        self._strategies = strategies
        self._trace_writer = trace_writer

    async def answer_stream(
        self, repository_id: str, question: str, mode: AnswerMode, history: Sequence[ChatTurn]
    ) -> AsyncIterator[AnswerStreamEvent]:
        scope_result = self._scope_guard.check(question)
        if not scope_result.is_allowed:
            yield ErrorEvent(message=scope_result.rejection_reason or "question rejected")
            return
        repository = await self._repository_store.get(repository_id)
        if repository is None:
            yield ErrorEvent(message="repository not found")
            return
        if repository.status is not IngestionStatus.READY:
            yield ErrorEvent(
                message=f"repository is not ready yet (status: {repository.status.value})"
            )
            return

        trace_steps: list[TraceStep] = []
        pending_tool_calls: list[tuple[ToolCallEvent, float]] = []
        async for event in self._strategies[mode].answer_stream(repository_id, question, history):
            if isinstance(event, ToolCallEvent):
                pending_tool_calls.append((event, time.monotonic()))
            elif isinstance(event, ToolResultEvent) and pending_tool_calls:
                call_event, call_started_at_seconds = pending_tool_calls.pop(0)
                trace_steps.append(TraceStep(
                    step_kind="tool_call",
                    name=event.tool_name,
                    arguments_json=json.dumps(call_event.arguments),
                    summary=event.summary,
                    duration_ms=int((time.monotonic() - call_started_at_seconds) * 1000),
                ))
            elif isinstance(event, AnswerRestartEvent):
                trace_steps.append(TraceStep(
                    step_kind="model_call", name="citation_retry",
                    arguments_json="{}", summary=event.reason, duration_ms=0,
                ))
            elif isinstance(event, AnswerCompletedEvent):
                await self._write_trace(repository_id, question, mode, trace_steps, event.answer)
            yield event

    async def _write_trace(
        self, repository_id: str, question: str, mode: AnswerMode,
        trace_steps: list[TraceStep], answer: Answer,
    ) -> None:
        trace = QueryTrace(
            trace_id=uuid.uuid4().hex,
            repository_id=repository_id,
            question=question,
            mode=mode,
            steps=trace_steps,
            answer_text=answer.text,
            citations=answer.citations,
            is_grounded=answer.is_grounded,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            estimated_cost_usd=answer.estimated_cost_usd,
            latency_ms=answer.latency_ms,
            created_at=datetime.now(UTC),
        )
        try:
            await self._trace_writer.write_trace(trace)
        except Exception as trace_error:  # noqa: BLE001
            # observability must never break the answer stream — log and continue
            logger.error("trace_write_failed", trace_id=trace.trace_id, error=str(trace_error))
