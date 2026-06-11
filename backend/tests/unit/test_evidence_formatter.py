from codedoc.application.answering.evidence_formatter import EvidenceFormatter
from codedoc.application.ports.searching import ChunkSearchHit, FileSpan
from codedoc.domain.chunk import CodeChunk, SymbolKind


def _hit(file_path: str, start_line: int, end_line: int, code: str) -> ChunkSearchHit:
    chunk = CodeChunk(
        chunk_id=f"repo1:{file_path}:{start_line}-{end_line}",
        repository_id="repo1",
        file_path=file_path,
        language="python",
        start_line=start_line,
        end_line=end_line,
        symbol_name="example_symbol",
        symbol_kind=SymbolKind.FUNCTION,
        enclosing_scope=None,
        docstring=None,
        code=code,
    )
    return ChunkSearchHit(chunk=chunk, score=1.0)


def test_search_hits_are_wrapped_in_evidence_blocks() -> None:
    formatter = EvidenceFormatter(max_evidence_tokens_per_result=2000)
    formatted = formatter.format_search_hits(
        [_hit("src/auth.py", 10, 12, "def login():\n    pass")]
    )
    assert formatted.startswith('<evidence tool="search_code" source="src/auth.py:10-12">')
    assert formatted.rstrip().endswith("</evidence>")
    assert "def login():" in formatted


def test_oversized_content_is_truncated_middle_out() -> None:
    formatter = EvidenceFormatter(max_evidence_tokens_per_result=100)  # budget: ~400 chars
    long_code = "HEAD_MARKER " + ("filler " * 500) + " TAIL_MARKER"
    formatted = formatter.format_search_hits([_hit("src/big.py", 1, 999, long_code)])
    assert "HEAD_MARKER" in formatted
    assert "TAIL_MARKER" in formatted
    assert "[truncated" in formatted
    assert len(formatted) < len(long_code)


def test_file_span_and_symbol_chunks_use_their_tool_names() -> None:
    formatter = EvidenceFormatter(max_evidence_tokens_per_result=2000)
    span_block = formatter.format_file_span(
        FileSpan(file_path="src/app.py", start_line=5, end_line=6, content="alpha\nbeta")
    )
    assert '<evidence tool="read_file_span" source="src/app.py:5-6">' in span_block
    symbol_block = formatter.format_symbol_chunks([_hit("src/auth.py", 10, 12, "code").chunk])
    assert '<evidence tool="find_symbol" source="src/auth.py:10-12">' in symbol_block


def test_structure_renders_an_indented_tree() -> None:
    formatter = EvidenceFormatter(max_evidence_tokens_per_result=2000)
    tree_block = formatter.format_structure(["src/app.py", "src/auth/login.py", "README.md"])
    assert '<evidence tool="list_repository_structure" source="repository">' in tree_block
    assert "src/" in tree_block and "login.py" in tree_block and "README.md" in tree_block
