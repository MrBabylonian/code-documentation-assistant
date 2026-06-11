from codedoc.application.answering.citation_parser import CitationParser
from codedoc.domain.answer import Citation


def test_parses_strips_and_deduplicates_citation_tokens() -> None:
    answer_text = (
        "Login happens in `authenticate_user` [cite: src/auth.py:10-42]. "
        "It hashes passwords [cite: src/auth.py:10-42] and stores sessions "
        "[cite: src/session.py:5-20]."
    )
    display_text, citations = CitationParser().parse(answer_text)
    assert citations == [
        Citation(file_path="src/auth.py", start_line=10, end_line=42),
        Citation(file_path="src/session.py", start_line=5, end_line=20),
    ]
    assert "[cite:" not in display_text
    assert "Login happens in `authenticate_user`." in display_text


def test_malformed_tokens_are_removed_but_not_returned() -> None:
    display_text, citations = CitationParser().parse("Broken [cite: src/a.py:42-10] reference.")
    assert citations == []
    assert "[cite:" not in display_text


def test_no_citations_yields_unchanged_text() -> None:
    display_text, citations = CitationParser().parse("Plain answer.")
    assert display_text == "Plain answer."
    assert citations == []
