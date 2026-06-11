from codedoc.application.answering.citation_parser import CitationParser
from codedoc.application.answering.citation_validator import CitationValidator
from codedoc.application.answering.evidence_formatter import EvidenceFormatter
from codedoc.application.answering.prompt_loader import SystemPromptLoader
from codedoc.application.answering.token_cost_calculator import TokenCostCalculator
from codedoc.application.ports.indexing import EmbeddedChunk
from codedoc.domain.chat import AnswerMode
from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.streaming import (
    AnswerCompletedEvent,
    AnswerRestartEvent,
    ErrorEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from codedoc.infrastructure.agents.agent_toolset import AgentToolset
from codedoc.infrastructure.agents.agentic_answer_strategy import AgenticAnswerStrategy
from tests.unit.chat_model_fakes import ToolCallingScriptedChatModel
from tests.unit.fakes import DeterministicEmbeddings, InMemoryChunkStore, InMemoryFileStore


async def _seeded_stores() -> tuple[InMemoryChunkStore, InMemoryFileStore]:
    chunk_store = InMemoryChunkStore()
    auth_chunk = CodeChunk(
        chunk_id=build_chunk_id("repo1", "src/auth.py", 10, 42), repository_id="repo1",
        file_path="src/auth.py", language="python", start_line=10, end_line=42,
        symbol_name="authenticate_user", symbol_kind=SymbolKind.FUNCTION,
        enclosing_scope=None, docstring=None,
        code="def authenticate_user():\n    validate_password()",
    )
    await chunk_store.write_chunks([EmbeddedChunk(chunk=auth_chunk, embedding=[0.0])])
    return chunk_store, InMemoryFileStore()


def _build_strategy(
    chat_model: ToolCallingScriptedChatModel,
    chunk_store: InMemoryChunkStore,
    file_store: InMemoryFileStore,
    max_tool_calls: int = 8,
) -> AgenticAnswerStrategy:
    def toolset_factory(repository_id: str) -> AgentToolset:
        return AgentToolset(
            repository_id=repository_id, chunk_searcher=chunk_store,
            file_content_reader=file_store, embeddings=DeterministicEmbeddings(),
            evidence_formatter=EvidenceFormatter(max_evidence_tokens_per_result=2000),
            search_top_k=5,
        )

    return AgenticAnswerStrategy(
        chat_model=chat_model,
        toolset_factory=toolset_factory,
        citation_parser=CitationParser(),
        citation_validator=CitationValidator(),
        prompt_loader=SystemPromptLoader(),
        token_cost_calculator=TokenCostCalculator(0.75, 4.50),
        max_tool_calls=max_tool_calls,
        max_history_turns=4,
        model_name="scripted-agent-model",
    )


async def test_tool_loop_emits_events_and_grounds_the_answer() -> None:
    chat_model = ToolCallingScriptedChatModel(scripted_turns=[
        {"tool_calls": [{"name": "search_code", "args": {"query": "authenticate password"}}]},
        {"text": "Authentication is `authenticate_user` [cite: src/auth.py:10-42]."},
    ])
    chunk_store, file_store = await _seeded_stores()
    strategy = _build_strategy(chat_model, chunk_store, file_store)

    events = [
        event async for event in strategy.answer_stream("repo1", "where is auth?", history=())
    ]

    tool_call_events = [event for event in events if isinstance(event, ToolCallEvent)]
    tool_result_events = [event for event in events if isinstance(event, ToolResultEvent)]
    assert [event.tool_name for event in tool_call_events] == ["search_code"]
    assert [event.tool_name for event in tool_result_events] == ["search_code"]
    completed_event = events[-1]
    assert isinstance(completed_event, AnswerCompletedEvent)
    assert completed_event.answer.is_grounded is True
    assert completed_event.answer.mode is AnswerMode.AGENTIC
    assert completed_event.answer.citations[0].file_path == "src/auth.py"
    assert completed_event.answer.input_tokens > 0


async def test_tool_budget_exhaustion_yields_error_event() -> None:
    chat_model = ToolCallingScriptedChatModel(scripted_turns=[
        # the same tool call forever — never a final text answer
        {"tool_calls": [{"name": "search_code", "args": {"query": "authenticate"}}]},
    ])
    chunk_store, file_store = await _seeded_stores()
    strategy = _build_strategy(chat_model, chunk_store, file_store, max_tool_calls=2)

    events = [event async for event in strategy.answer_stream("repo1", "where?", history=())]

    assert isinstance(events[-1], ErrorEvent)
    assert "budget" in events[-1].message


async def test_zero_citation_final_answer_retries_once_without_tools() -> None:
    chat_model = ToolCallingScriptedChatModel(scripted_turns=[
        {"tool_calls": [{"name": "search_code", "args": {"query": "authenticate"}}]},
        {"text": "It is authenticate_user, somewhere."},     # no citations → corrective retry
        {"text": "It is `authenticate_user` [cite: src/auth.py:10-42]."},
    ])
    chunk_store, file_store = await _seeded_stores()
    strategy = _build_strategy(chat_model, chunk_store, file_store)

    events = [event async for event in strategy.answer_stream("repo1", "where?", history=())]

    assert len([event for event in events if isinstance(event, AnswerRestartEvent)]) == 1
    completed_event = events[-1]
    assert isinstance(completed_event, AnswerCompletedEvent)
    assert completed_event.answer.is_grounded is True
    assert chat_model.turn_cursor == 3
