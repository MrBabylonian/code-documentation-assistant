from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from codedoc.domain.chat import ChatTurn
from codedoc.domain.streaming import AnswerStreamEvent


class AnswerStrategy(Protocol):
    def answer_stream(
        self, repository_id: str, question: str, history: Sequence[ChatTurn]
    ) -> AsyncIterator[AnswerStreamEvent]: ...
