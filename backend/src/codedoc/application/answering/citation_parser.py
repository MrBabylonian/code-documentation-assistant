import re

from codedoc.domain.answer import Citation

CITATION_TOKEN_PATTERN = re.compile(r"\[cite:\s*([^\s\]]+):(\d+)-(\d+)\]")


class CitationParser:
    """Extracts [cite: path:start-end] tokens; returns display text with tokens removed."""

    def parse(self, answer_text: str) -> tuple[str, list[Citation]]:
        citations: list[Citation] = []
        for token_match in CITATION_TOKEN_PATTERN.finditer(answer_text):
            start_line = int(token_match.group(2))
            end_line = int(token_match.group(3))
            if start_line > end_line:
                continue  # malformed token: stripped from text below, never returned
            citation = Citation(
                file_path=token_match.group(1), start_line=start_line, end_line=end_line
            )
            if citation not in citations:
                citations.append(citation)
        display_text = CITATION_TOKEN_PATTERN.sub("", answer_text)
        display_text = re.sub(r"[ \t]{2,}", " ", display_text)
        display_text = re.sub(r" +([.,;:!?])", r"\1", display_text)
        return display_text.strip(), citations
