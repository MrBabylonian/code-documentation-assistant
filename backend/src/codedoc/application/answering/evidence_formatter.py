from collections.abc import Sequence

from codedoc.application.ports.searching import ChunkSearchHit, FileSpan
from codedoc.domain.chunk import CodeChunk

ESTIMATED_CHARS_PER_TOKEN = 4
TRUNCATION_MARKER_TEMPLATE = "\n… [truncated ~{token_count} estimated tokens] …\n"


class EvidenceFormatter:
    """Wraps retrieval results in delimited evidence blocks; token-budgets each block.

    The wrapper is a guardrail: system prompts declare evidence blocks to be data,
    never instructions.
    """

    def __init__(self, max_evidence_tokens_per_result: int) -> None:
        self._max_content_chars = max_evidence_tokens_per_result * ESTIMATED_CHARS_PER_TOKEN

    def format_search_hits(self, hits: Sequence[ChunkSearchHit]) -> str:
        return "\n".join(
            self._wrap("search_code", self._source_of(hit.chunk), hit.chunk.code) for hit in hits
        )

    def format_file_span(self, file_span: FileSpan) -> str:
        source = f"{file_span.file_path}:{file_span.start_line}-{file_span.end_line}"
        return self._wrap("read_file_span", source, file_span.content)

    def format_structure(self, file_paths: Sequence[str]) -> str:
        rendered_lines: list[str] = []
        previous_segments: list[str] = []
        for file_path in sorted(file_paths):
            segments = file_path.split("/")
            shared_count = 0
            for segment_index in range(min(len(segments) - 1, len(previous_segments))):
                if segments[segment_index] != previous_segments[segment_index]:
                    break
                shared_count = segment_index + 1
            for directory_index in range(shared_count, len(segments) - 1):
                rendered_lines.append("  " * directory_index + segments[directory_index] + "/")
            rendered_lines.append("  " * (len(segments) - 1) + segments[-1])
            previous_segments = segments[:-1]
        return self._wrap("list_repository_structure", "repository", "\n".join(rendered_lines))

    def format_symbol_chunks(self, chunks: Sequence[CodeChunk]) -> str:
        return "\n".join(
            self._wrap("find_symbol", self._source_of(chunk), chunk.code) for chunk in chunks
        )

    @staticmethod
    def _source_of(chunk: CodeChunk) -> str:
        return f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"

    def _wrap(self, tool_name: str, source: str, content: str) -> str:
        budgeted_content = self._truncate_middle_out(content)
        return f'<evidence tool="{tool_name}" source="{source}">\n{budgeted_content}\n</evidence>'

    def _truncate_middle_out(self, content: str) -> str:
        if len(content) <= self._max_content_chars:
            return content
        half_budget_chars = self._max_content_chars // 2
        dropped_token_count = (len(content) - self._max_content_chars) // ESTIMATED_CHARS_PER_TOKEN
        marker = TRUNCATION_MARKER_TEMPLATE.format(token_count=dropped_token_count)
        return content[:half_budget_chars] + marker + content[-half_budget_chars:]
