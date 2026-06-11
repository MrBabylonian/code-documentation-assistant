from collections.abc import Sequence

from codedoc.application.answering.citation_parser import CitationParser
from codedoc.application.answering.citation_validator import CitationValidator
from codedoc.application.answering.evidence_formatter import EvidenceFormatter
from codedoc.application.answering.prompt_loader import SystemPromptLoader
from codedoc.application.answering.single_shot_answer_strategy import SingleShotAnswerStrategy
from codedoc.application.answering.token_cost_calculator import TokenCostCalculator
from codedoc.application.ports.indexing import EmbeddedChunk
from codedoc.domain.chat import AnswerMode, ChatTurn
from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.streaming import (
    AnswerCompletedEvent,
    AnswerRestartEvent,
    AnswerStreamEvent,
    AnswerTokenEvent,
)
from tests.unit.chat_model_fakes import ScriptedChatModel
from tests.unit.fakes import DeterministicEmbeddings, InMemoryChunkStore


async def _seeded_chunk_store() -> InMemoryChunkStore:
    chunk_store = InMemoryChunkStore()
    auth_chunk = CodeChunk(
        chunk_id=build_chunk_id("repo1", "src/auth.py", 10, 42),
        repository_id="repo1",
        file_path="src/auth.py",
        language="python",
        start_line=10,
        end_line=42,
        symbol_name="authenticate_user",
        symbol_kind=SymbolKind.FUNCTION,
        enclosing_scope=None,
        docstring=None,
        # "is the authentication" makes the chunk match the test question under
        # InMemoryChunkStore's term-count scoring, so evidence spans are non-empty.
        code="def authenticate_user():\n    # this is the authentication entry point\n"
        "    validate_password()",
    )
    await chunk_store.write_chunks([EmbeddedChunk(chunk=auth_chunk, embedding=[0.0])])
    return chunk_store


def _build_strategy(
    chat_model: ScriptedChatModel, chunk_store: InMemoryChunkStore
) -> SingleShotAnswerStrategy:
    return SingleShotAnswerStrategy(
        chat_model=chat_model,
        embeddings=DeterministicEmbeddings(),
        chunk_searcher=chunk_store,
        evidence_formatter=EvidenceFormatter(max_evidence_tokens_per_result=2000),
        citation_parser=CitationParser(),
        citation_validator=CitationValidator(),
        prompt_loader=SystemPromptLoader(),
        token_cost_calculator=TokenCostCalculator(0.75, 4.50),
        search_top_k=4,
        max_history_turns=2,
        model_name="scripted-model",
    )


async def _collect(
    strategy: SingleShotAnswerStrategy, history: Sequence[ChatTurn] = ()
) -> list[AnswerStreamEvent]:
    return [
        event
        async for event in strategy.answer_stream("repo1", "where is authentication?", history)
    ]


async def test_streams_tokens_and_completes_with_grounded_answer() -> None:
    chat_model = ScriptedChatModel(
        scripted_responses=[
            "Authentication lives in `authenticate_user` [cite: src/auth.py:10-42]."
        ]
    )
    events = await _collect(_build_strategy(chat_model, await _seeded_chunk_store()))

    token_events = [event for event in events if isinstance(event, AnswerTokenEvent)]
    assert "".join(event.text for event in token_events).startswith("Authentication lives")
    completed_event = events[-1]
    assert isinstance(completed_event, AnswerCompletedEvent)
    answer = completed_event.answer
    assert answer.is_grounded is True
    assert answer.citations[0].file_path == "src/auth.py"
    assert "[cite:" not in answer.text
    assert answer.mode is AnswerMode.SINGLE_SHOT
    assert answer.input_tokens == 100 and answer.output_tokens == 20
    assert answer.estimated_cost_usd > 0
    assert answer.latency_ms >= 0


async def test_zero_citation_answer_triggers_exactly_one_retry() -> None:
    chat_model = ScriptedChatModel(
        scripted_responses=[
            "Authentication is somewhere in the code.",  # no citations → retry
            "It is `authenticate_user` [cite: src/auth.py:10-42].",
        ]
    )
    events = await _collect(_build_strategy(chat_model, await _seeded_chunk_store()))

    restart_events = [event for event in events if isinstance(event, AnswerRestartEvent)]
    assert len(restart_events) == 1
    completed_event = events[-1]
    assert isinstance(completed_event, AnswerCompletedEvent)
    assert completed_event.answer.is_grounded is True
    assert chat_model.response_cursor == 2


async def test_persistent_zero_citations_completes_ungrounded_without_second_retry() -> None:
    chat_model = ScriptedChatModel(scripted_responses=["No citations here.", "Still none."])
    events = await _collect(_build_strategy(chat_model, await _seeded_chunk_store()))

    assert len([event for event in events if isinstance(event, AnswerRestartEvent)]) == 1
    completed_event = events[-1]
    assert isinstance(completed_event, AnswerCompletedEvent)
    assert completed_event.answer.is_grounded is False
    assert chat_model.response_cursor == 2  # exactly two model calls, never a third


async def test_history_is_capped_to_max_history_turns() -> None:
    chat_model = ScriptedChatModel(scripted_responses=["Answer [cite: src/auth.py:10-42]."])
    long_history = [
        ChatTurn(role="user" if turn_index % 2 == 0 else "assistant", text=f"turn {turn_index}")
        for turn_index in range(6)
    ]
    await _collect(_build_strategy(chat_model, await _seeded_chunk_store()), history=long_history)

    received_messages = chat_model.received_message_batches[0]
    # system + capped history (2) + question = 4
    assert len(received_messages) == 4
    assert "turn 4" in str(received_messages[1].content)
    assert "turn 5" in str(received_messages[2].content)
