import time
from collections.abc import AsyncIterator, Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from codedoc.application.answering.citation_parser import CitationParser
from codedoc.application.answering.citation_validator import CitationValidator
from codedoc.application.answering.prompt_loader import SystemPromptLoader
from codedoc.application.answering.token_cost_calculator import TokenCostCalculator
from codedoc.domain.answer import Answer
from codedoc.domain.chat import AnswerMode, ChatTurn
from codedoc.domain.streaming import (
    AnswerCompletedEvent,
    AnswerRestartEvent,
    AnswerStreamEvent,
    AnswerTokenEvent,
    ErrorEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from codedoc.infrastructure.agents.agent_toolset import AgentToolset

TOOL_RESULT_SUMMARY_LENGTH_CHARS = 200
CITATION_RETRY_INSTRUCTION = (
    "Your answer contained no [cite: ...] citations. Rewrite it citing every claim "
    "with [cite: <file_path>:<start_line>-<end_line>] tokens, using only the evidence "
    "already retrieved above."
)
BUDGET_EXHAUSTED_MESSAGE = (
    "The agent exceeded its tool budget without producing an answer. Try a more specific question."
)


class AgenticAnswerStrategy:
    """LangGraph tool loop: llm ⇄ tools until a final text answer or the budget stops it."""

    def __init__(
        self,
        chat_model: BaseChatModel,
        toolset_factory: Callable[[str], AgentToolset],
        citation_parser: CitationParser,
        citation_validator: CitationValidator,
        prompt_loader: SystemPromptLoader,
        token_cost_calculator: TokenCostCalculator,
        max_tool_calls: int,
        max_history_turns: int,
        model_name: str,
    ) -> None:
        self._chat_model = chat_model
        self._toolset_factory = toolset_factory
        self._citation_parser = citation_parser
        self._citation_validator = citation_validator
        self._prompt_loader = prompt_loader
        self._token_cost_calculator = token_cost_calculator
        self._max_tool_calls = max_tool_calls
        self._max_history_turns = max_history_turns
        self._model_name = model_name

    async def answer_stream(
        self, repository_id: str, question: str, history: Sequence[ChatTurn]
    ) -> AsyncIterator[AnswerStreamEvent]:
        started_at_seconds = time.monotonic()
        toolset = self._toolset_factory(repository_id)  # per-request: accumulates evidence
        graph = self._build_graph(toolset)
        initial_messages = self._build_messages(question, history)

        answer_text = ""
        total_input_tokens = 0
        total_output_tokens = 0
        final_messages: list[BaseMessage] = list(initial_messages)
        try:
            stream = graph.astream(
                {"messages": initial_messages},
                # one llm→tools round = 2 supersteps; +1 for the final llm answer
                {"recursion_limit": 2 * self._max_tool_calls + 1},
                stream_mode=["messages", "updates"],
                version="v2",
            )
            async for stream_part in stream:
                # comparing on the indexed literal narrows the tagged StreamPart union
                if stream_part["type"] == "updates":
                    for node_update in stream_part["data"].values():
                        for updated_message in node_update.get("messages", []):
                            final_messages = [*final_messages, updated_message]
                            if isinstance(updated_message, AIMessage):
                                message_usage = updated_message.usage_metadata
                                if message_usage is not None:
                                    total_input_tokens += message_usage["input_tokens"]
                                    total_output_tokens += message_usage["output_tokens"]
                                for tool_call in updated_message.tool_calls:
                                    yield ToolCallEvent(
                                        tool_name=tool_call["name"],
                                        arguments=dict(tool_call["args"]),
                                    )
                                if not updated_message.tool_calls and isinstance(
                                    updated_message.content, str
                                ):
                                    answer_text = updated_message.content
                            elif isinstance(updated_message, ToolMessage):
                                tool_result_text = str(updated_message.content)
                                yield ToolResultEvent(
                                    tool_name=updated_message.name or "tool",
                                    summary=tool_result_text[:TOOL_RESULT_SUMMARY_LENGTH_CHARS],
                                )
                elif stream_part["type"] == "messages":
                    message_chunk = stream_part["data"][0]  # data is (message, metadata)
                    if (
                        isinstance(message_chunk, AIMessageChunk)
                        and not message_chunk.tool_call_chunks
                        and isinstance(message_chunk.content, str)
                        and message_chunk.content
                    ):
                        yield AnswerTokenEvent(text=message_chunk.content)
        except GraphRecursionError:
            if not answer_text:
                yield ErrorEvent(message=BUDGET_EXHAUSTED_MESSAGE)
                return

        display_text, parsed_citations = self._citation_parser.parse(answer_text)
        if not parsed_citations:
            yield AnswerRestartEvent(reason="answer had no citations")
            # one direct no-tools retry — a second graph run would double the token bill
            corrective_messages = [
                *final_messages,
                HumanMessage(content=CITATION_RETRY_INSTRUCTION),
            ]
            retry_response = await self._chat_model.ainvoke(corrective_messages)
            if retry_response.usage_metadata is not None:
                total_input_tokens += retry_response.usage_metadata["input_tokens"]
                total_output_tokens += retry_response.usage_metadata["output_tokens"]
            answer_text = str(retry_response.content)
            for answer_word in answer_text.split(" "):
                yield AnswerTokenEvent(text=answer_word + " ")
            display_text, parsed_citations = self._citation_parser.parse(answer_text)

        validation_result = self._citation_validator.validate(
            parsed_citations, toolset.collected_evidence
        )
        yield AnswerCompletedEvent(
            answer=Answer(
                text=display_text,
                citations=validation_result.valid_citations,
                is_grounded=validation_result.is_grounded,
                mode=AnswerMode.AGENTIC,
                model_name=self._model_name,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                estimated_cost_usd=self._token_cost_calculator.estimate_cost_usd(
                    total_input_tokens, total_output_tokens
                ),
                latency_ms=int((time.monotonic() - started_at_seconds) * 1000),
            )
        )

    def _build_graph(
        self, toolset: AgentToolset
    ) -> CompiledStateGraph[MessagesState, None, MessagesState, MessagesState]:
        tools = toolset.build_tools()
        model_with_tools = self._chat_model.bind_tools(tools)

        async def call_model(state: MessagesState) -> dict[str, list[BaseMessage]]:
            response_message = await model_with_tools.ainvoke(state["messages"])
            return {"messages": [response_message]}

        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("llm", call_model)
        # the node name MUST be the literal "tools": tools_condition routes to it by that name
        graph_builder.add_node("tools", ToolNode(tools))
        graph_builder.add_edge(START, "llm")
        graph_builder.add_conditional_edges("llm", tools_condition, ["tools", END])
        graph_builder.add_edge("tools", "llm")
        return graph_builder.compile()

    def _build_messages(self, question: str, history: Sequence[ChatTurn]) -> list[AnyMessage]:
        messages: list[AnyMessage] = [
            SystemMessage(content=self._prompt_loader.load("agentic_system_prompt"))
        ]
        for chat_turn in list(history)[-self._max_history_turns :]:
            if chat_turn.role == "user":
                messages.append(HumanMessage(content=chat_turn.text))
            else:
                messages.append(AIMessage(content=chat_turn.text))
        messages.append(HumanMessage(content=question))
        return messages
