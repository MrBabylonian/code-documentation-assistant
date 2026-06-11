from pydantic import BaseModel, Field

from codedoc.domain.chat import AnswerMode

MAX_HISTORY_TURNS_ACCEPTED = 50


class ChatTurnPayload(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str


class AnswerRequest(BaseModel):
    question: str
    mode: AnswerMode
    history: list[ChatTurnPayload] = Field(
        default_factory=list, max_length=MAX_HISTORY_TURNS_ACCEPTED
    )


class FileSpanResponse(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    content: str
