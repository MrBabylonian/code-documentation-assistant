from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from codedoc.domain.answer import Citation
from codedoc.domain.chat import AnswerMode


@dataclass(frozen=True)
class TraceStep:
    step_kind: Literal["tool_call", "model_call"]
    name: str
    arguments_json: str
    summary: str
    duration_ms: int


@dataclass
class QueryTrace:
    trace_id: str
    repository_id: str
    question: str
    mode: AnswerMode
    steps: list[TraceStep]
    answer_text: str
    citations: list[Citation]
    is_grounded: bool
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    created_at: datetime
