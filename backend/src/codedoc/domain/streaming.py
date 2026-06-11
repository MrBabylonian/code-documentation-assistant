from dataclasses import dataclass
from typing import Literal

from codedoc.domain.answer import Answer


@dataclass(frozen=True)
class ToolCallEvent:
    tool_name: str
    arguments: dict[str, object]
    kind: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True)
class ToolResultEvent:
    tool_name: str
    summary: str
    kind: Literal["tool_result"] = "tool_result"


@dataclass(frozen=True)
class AnswerTokenEvent:
    text: str
    kind: Literal["answer_token"] = "answer_token"


@dataclass(frozen=True)
class AnswerRestartEvent:
    reason: str
    kind: Literal["answer_restart"] = "answer_restart"


@dataclass(frozen=True)
class AnswerCompletedEvent:
    answer: Answer
    kind: Literal["answer_completed"] = "answer_completed"


@dataclass(frozen=True)
class ErrorEvent:
    message: str
    kind: Literal["error"] = "error"


AnswerStreamEvent = (
    ToolCallEvent
    | ToolResultEvent
    | AnswerTokenEvent
    | AnswerRestartEvent
    | AnswerCompletedEvent
    | ErrorEvent
)
