from codedoc.application.answering.citation_validator import CitationValidator
from codedoc.domain.answer import Citation


def _citation(file_path: str, start_line: int, end_line: int) -> Citation:
    return Citation(file_path=file_path, start_line=start_line, end_line=end_line)


def test_overlapping_citation_in_evidence_file_is_valid_and_grounded() -> None:
    result = CitationValidator().validate(
        citations=[_citation("src/auth.py", 15, 20)],
        evidence_spans=[_citation("src/auth.py", 10, 42)],
    )
    assert result.valid_citations == [_citation("src/auth.py", 15, 20)]
    assert result.invalid_citations == []
    assert result.is_grounded is True


def test_touching_ranges_count_as_overlap() -> None:
    result = CitationValidator().validate(
        citations=[_citation("src/auth.py", 42, 50)],
        evidence_spans=[_citation("src/auth.py", 10, 42)],
    )
    assert result.is_grounded is True


def test_wrong_file_or_disjoint_range_is_invalid() -> None:
    result = CitationValidator().validate(
        citations=[_citation("src/other.py", 15, 20), _citation("src/auth.py", 100, 120)],
        evidence_spans=[_citation("src/auth.py", 10, 42)],
    )
    assert result.valid_citations == []
    assert len(result.invalid_citations) == 2
    assert result.is_grounded is False


def test_no_citations_is_not_grounded() -> None:
    result = CitationValidator().validate(citations=[], evidence_spans=[_citation("a.py", 1, 2)])
    assert result.is_grounded is False
