from dataclasses import dataclass

OBVIOUS_ABUSE_SUBSTRINGS = (
    "ignore your instructions",
    "ignore previous instructions",
    "system prompt",
    "reveal your prompt",
    "jailbreak",
)


@dataclass(frozen=True)
class ScopeCheckResult:
    is_allowed: bool
    rejection_reason: str | None


class QuestionScopeGuard:
    """Cheap rule-based pre-check. The real guardrails are capability containment
    (read-only tools), the evidence-is-data prompt rules, and citation grounding —
    this guard just keeps obvious abuse from spending agent tokens."""

    def __init__(self, max_question_length_chars: int) -> None:
        self._max_question_length_chars = max_question_length_chars

    def check(self, question: str) -> ScopeCheckResult:
        stripped_question = question.strip()
        if not stripped_question:
            return ScopeCheckResult(False, "Please ask a question about the ingested repository.")
        if len(stripped_question) > self._max_question_length_chars:
            return ScopeCheckResult(
                False,
                f"That question is too long (over {self._max_question_length_chars} characters). "
                "Please ask something more focused.",
            )
        lowered_question = stripped_question.lower()
        if any(abuse_marker in lowered_question for abuse_marker in OBVIOUS_ABUSE_SUBSTRINGS):
            return ScopeCheckResult(
                False, "I can only answer questions about the ingested repository."
            )
        return ScopeCheckResult(True, None)
