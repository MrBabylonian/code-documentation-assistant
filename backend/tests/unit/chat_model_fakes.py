import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class ScriptedChatModel(BaseChatModel):
    """Streams pre-scripted responses word by word; records every prompt it receives.

    Pydantic model fields (BaseChatModel is a pydantic model — plain attribute
    assignment in __init__ does not work):
    """

    scripted_responses: list[str]
    received_message_batches: list[list[BaseMessage]] = []
    response_cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    def bind_tools(self, tools: Any, **bind_kwargs: Any) -> "ScriptedChatModel":
        return self

    def _next_response(self, messages: list[BaseMessage]) -> str:
        self.received_message_batches.append(list(messages))
        scripted_text = self.scripted_responses[
            min(self.response_cursor, len(self.scripted_responses) - 1)
        ]
        self.response_cursor += 1
        return scripted_text

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **generation_kwargs: Any,
    ) -> ChatResult:
        scripted_text = self._next_response(messages)
        response_message = AIMessage(
            content=scripted_text,
            usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        )
        return ChatResult(generations=[ChatGeneration(message=response_message)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **generation_kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        scripted_text = self._next_response(messages)
        words = scripted_text.split(" ")
        for word_index, word in enumerate(words):
            is_last_word = word_index == len(words) - 1
            chunk_text = word if is_last_word else word + " "
            chunk_message = AIMessageChunk(
                content=chunk_text,
                usage_metadata=(
                    {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
                    if is_last_word
                    else None
                ),
            )
            yield ChatGenerationChunk(message=chunk_message)


class ToolCallingScriptedChatModel(BaseChatModel):
    """Scripted model that can emit tool calls; ToolNode then executes REAL tools.

    Each script entry is either {"tool_calls": [{"name": ..., "args": {...}}]}
    or {"text": "..."}.
    """

    scripted_turns: list[dict[str, Any]]
    turn_cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "tool-calling-scripted-chat-model"

    def bind_tools(self, tools: Any, **bind_kwargs: Any) -> "ToolCallingScriptedChatModel":
        return self

    def _next_message(self) -> AIMessage:
        scripted_turn = self.scripted_turns[min(self.turn_cursor, len(self.scripted_turns) - 1)]
        self.turn_cursor += 1
        if "tool_calls" in scripted_turn:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": tool_call["name"],
                        "args": tool_call["args"],
                        "id": f"call_{self.turn_cursor}_{tool_call_index}",
                        "type": "tool_call",
                    }
                    for tool_call_index, tool_call in enumerate(scripted_turn["tool_calls"])
                ],
                usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
            )
        return AIMessage(
            content=scripted_turn["text"],
            usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **generation_kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next_message())])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **generation_kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        scripted_message = self._next_message()
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content=scripted_message.content,
                tool_call_chunks=[
                    {
                        "name": tool_call["name"],
                        "args": json.dumps(tool_call["args"]),
                        "id": tool_call["id"],
                        "index": tool_call_index,
                        "type": "tool_call_chunk",
                    }
                    for tool_call_index, tool_call in enumerate(scripted_message.tool_calls)
                ],
                usage_metadata=scripted_message.usage_metadata,
            )
        )
