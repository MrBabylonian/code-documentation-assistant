from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.source_file import SourceFile


class LineWindowChunkingStrategy:
    """Fallback chunking for non-code files: fixed line windows with overlap."""

    def __init__(self, window_line_count: int = 60, overlap_line_count: int = 10) -> None:
        if overlap_line_count >= window_line_count:
            raise ValueError("overlap must be smaller than the window")
        self._window_line_count = window_line_count
        self._overlap_line_count = overlap_line_count

    def chunk(self, repository_id: str, source_file: SourceFile) -> list[CodeChunk]:
        content_lines = source_file.content.splitlines()
        total_line_count = len(content_lines)
        if total_line_count == 0:
            return []

        step_line_count = self._window_line_count - self._overlap_line_count
        spans: list[tuple[int, int]] = []
        window_start = 1
        while window_start <= total_line_count:
            window_end = min(window_start + self._window_line_count - 1, total_line_count)
            window_length = window_end - window_start + 1
            if spans and window_length < self._overlap_line_count:
                previous_start, _previous_end = spans[-1]
                spans[-1] = (previous_start, window_end)
                break
            spans.append((window_start, window_end))
            if window_end == total_line_count:
                break
            window_start += step_line_count

        return [
            CodeChunk(
                chunk_id=build_chunk_id(
                    repository_id, source_file.relative_path, span_start, span_end
                ),
                repository_id=repository_id,
                file_path=source_file.relative_path,
                language=source_file.language,
                start_line=span_start,
                end_line=span_end,
                symbol_name=None,
                symbol_kind=SymbolKind.TEXT_BLOCK,
                enclosing_scope=None,
                docstring=None,
                code="\n".join(content_lines[span_start - 1 : span_end]),
            )
            for span_start, span_end in spans
        ]
