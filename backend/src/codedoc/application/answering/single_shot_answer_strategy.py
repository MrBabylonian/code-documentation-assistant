import time
from collections.abc import AsyncIterator, Sequence

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from codedoc.application.answering.citation_parser import CitationParser
from codedoc.application.answering.citation_validator import CitationValidator
from codedoc.application.answering.evidence_formatter import EvidenceFormatter
from codedoc.application.answering.prompt_loader import SystemPromptLoader
from codedoc.application.answering.token_cost_calculator import TokenCostCalculator
from codedoc.application.ports.searching import ChunkSearcher, ChunkSearchHit
from codedoc.domain.answer import Answer, Citation
from codedoc.domain.chat import AnswerMode, ChatTurn
from codedoc.domain.streaming import (
    AnswerCompletedEvent,
    AnswerRestartEvent,
    AnswerStreamEvent,
    AnswerTokenEvent,
)

CITATION_RETRY_INSTRUCTION = (
    "Your answer contained no [cite: ...] citations. Rewrite it citing every claim "
    "with [cite: <file_path>:<start_line>-<end_line>] tokens, using only the evidence provided."
)


class SingleShotAnswerStrategy:
    """One retrieval pass, one completion; retries once when the answer has no citations."""

    def __init__(
        self,
        chat_model: BaseChatModel,
        embeddings: Embeddings,
        chunk_searcher: ChunkSearcher,
        evidence_formatter: EvidenceFormatter,
        citation_parser: CitationParser,
        citation_validator: CitationValidator,
        prompt_loader: SystemPromptLoader,
        token_cost_calculator: TokenCostCalculator,
        search_top_k: int,
        max_history_turns: int,
        model_name: str,
    ) -> None:
        self._chat_model = chat_model
        self._embeddings = embeddings
        self._chunk_searcher = chunk_searcher
        self._evidence_formatter = evidence_formatter
        self._citation_parser = citation_parser
        self._citation_validator = citation_validator
        self._prompt_loader = prompt_loader
        self._token_cost_calculator = token_cost_calculator
        self._search_top_k = search_top_k
        self._max_history_turns = max_history_turns
        self._model_name = model_name

    async def answer_stream(
        self, repository_id: str, question: str, history: Sequence[ChatTurn]
    ) -> AsyncIterator[AnswerStreamEvent]:
        started_at_seconds = time.monotonic()
        query_embedding = await self._embeddings.aembed_query(question)
        search_hits = await self._chunk_searcher.search(
            repository_id, question, query_embedding, self._search_top_k
        )
        evidence_spans = [
            Citation(
                file_path=hit.chunk.file_path,
                start_line=hit.chunk.start_line,
                end_line=hit.chunk.end_line,
            )
            for hit in search_hits
        ]
        messages = self._build_messages(question, history, search_hits)

        total_input_tokens = 0
        total_output_tokens = 0
        answer_text = ""
        for attempt_index in range(2):  # initial attempt + at most one citation retry
            answer_text = ""
            async for chunk in self._chat_model.astream(messages):
                # .text is a str subclass (TextAccessor) in langchain 1.x; normalize to plain str
                chunk_text = str(chunk.text)
                if chunk_text:
                    answer_text += chunk_text
                    yield AnswerTokenEvent(text=chunk_text)
                if chunk.usage_metadata is not None:
                    total_input_tokens += chunk.usage_metadata["input_tokens"]
                    total_output_tokens += chunk.usage_metadata["output_tokens"]
            display_text, parsed_citations = self._citation_parser.parse(answer_text)
            if parsed_citations or attempt_index == 1:
                break
            yield AnswerRestartEvent(reason="answer had no citations")
            messages = [
                *messages,
                AIMessage(content=answer_text),
                HumanMessage(content=CITATION_RETRY_INSTRUCTION),
            ]

        display_text, parsed_citations = self._citation_parser.parse(answer_text)
        validation_result = self._citation_validator.validate(parsed_citations, evidence_spans)
        yield AnswerCompletedEvent(
            answer=Answer(
                text=display_text,
                citations=validation_result.valid_citations,
                is_grounded=validation_result.is_grounded,
                mode=AnswerMode.SINGLE_SHOT,
                model_name=self._model_name,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                estimated_cost_usd=self._token_cost_calculator.estimate_cost_usd(
                    total_input_tokens, total_output_tokens
                ),
                latency_ms=int((time.monotonic() - started_at_seconds) * 1000),
            )
        )

    def _build_messages(
        self, question: str, history: Sequence[ChatTurn], search_hits: list[ChunkSearchHit]
    ) -> list[BaseMessage]:
        formatted_evidence = self._evidence_formatter.format_search_hits(search_hits)
        messages: list[BaseMessage] = [
            SystemMessage(content=self._prompt_loader.load("single_shot_system_prompt"))
        ]
        for chat_turn in list(history)[-self._max_history_turns :]:
            if chat_turn.role == "user":
                messages.append(HumanMessage(content=chat_turn.text))
            else:
                messages.append(AIMessage(content=chat_turn.text))
        messages.append(HumanMessage(content=f"{question}\n\nEvidence:\n{formatted_evidence}"))
        return messages
