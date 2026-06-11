from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class AnswerMode(StrEnum):
    AGENTIC = "agentic"
    SINGLE_SHOT = "single_shot"


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    text: str
