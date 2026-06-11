from collections.abc import Sequence
from dataclasses import dataclass

from codedoc.domain.answer import Citation


@dataclass(frozen=True)
class CitationValidationResult:
    valid_citations: list[Citation]
    invalid_citations: list[Citation]
    is_grounded: bool


class CitationValidator:
    """A citation is valid iff its file appears in evidence AND line ranges overlap."""

    def validate(
        self, citations: Sequence[Citation], evidence_spans: Sequence[Citation]
    ) -> CitationValidationResult:
        valid_citations: list[Citation] = []
        invalid_citations: list[Citation] = []
        for citation in citations:
            if any(self._overlaps(citation, evidence_span) for evidence_span in evidence_spans):
                valid_citations.append(citation)
            else:
                invalid_citations.append(citation)
        return CitationValidationResult(
            valid_citations=valid_citations,
            invalid_citations=invalid_citations,
            is_grounded=bool(valid_citations) and not invalid_citations,
        )

    @staticmethod
    def _overlaps(citation: Citation, evidence_span: Citation) -> bool:
        return (
            citation.file_path == evidence_span.file_path
            and citation.start_line <= evidence_span.end_line
            and citation.end_line >= evidence_span.start_line
        )
