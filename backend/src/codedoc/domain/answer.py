from dataclasses import dataclass

from codedoc.domain.chat import AnswerMode


@dataclass(frozen=True)
class Citation:
    file_path: str
    start_line: int
    end_line: int


@dataclass
class Answer:
    text: str
    citations: list[Citation]
    is_grounded: bool
    mode: AnswerMode
    model_name: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int

    def __post_init__(self) -> None:
        # defensive copy so callers cannot mutate a shared citations list after construction
        self.citations = list(self.citations)
