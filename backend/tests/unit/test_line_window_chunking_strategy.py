from codedoc.application.ingestion.chunking.line_window_chunking_strategy import (
    LineWindowChunkingStrategy,
)
from codedoc.domain.chunk import SymbolKind
from codedoc.domain.source_file import SourceFile


def _spans(
    content_line_count: int, window_line_count: int = 60, overlap_line_count: int = 10
) -> list[tuple[int, int]]:
    content = "\n".join(f"line {line_number}" for line_number in range(1, content_line_count + 1))
    source_file = SourceFile(relative_path="notes.md", content=content, language="markdown")
    strategy = LineWindowChunkingStrategy(
        window_line_count=window_line_count, overlap_line_count=overlap_line_count
    )
    return [(chunk.start_line, chunk.end_line) for chunk in strategy.chunk("repo1", source_file)]


def test_windows_overlap_and_cover_the_whole_file() -> None:
    assert _spans(130) == [(1, 60), (51, 110), (101, 130)]


def test_final_short_window_merges_into_previous() -> None:
    # third window would be 101-105: 5 lines < overlap 10 → merged into the second
    assert _spans(105) == [(1, 60), (51, 105)]


def test_single_window_file() -> None:
    assert _spans(40) == [(1, 40)]


def test_chunks_are_text_blocks_with_content() -> None:
    source_file = SourceFile(relative_path="notes.md", content="alpha\nbeta", language="markdown")
    chunks = LineWindowChunkingStrategy().chunk("repo1", source_file)
    assert chunks[0].symbol_kind is SymbolKind.TEXT_BLOCK
    assert chunks[0].symbol_name is None
    assert chunks[0].code == "alpha\nbeta"
    assert chunks[0].chunk_id == "repo1:notes.md:1-2"
