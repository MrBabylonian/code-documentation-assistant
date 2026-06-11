from codedoc.application.ingestion.chunking.chunking_strategy_resolver import (
    ChunkingStrategyResolver,
)
from codedoc.domain.chunk import CodeChunk
from codedoc.domain.source_file import SourceFile


class StubChunkingStrategy:
    """Protocol-satisfying stand-in; the resolver routes on identity, not behavior."""

    def chunk(self, repository_id: str, source_file: SourceFile) -> list[CodeChunk]:
        return []


def test_resolver_routes_code_languages_to_tree_sitter_and_rest_to_line_windows() -> None:
    tree_sitter_strategy = StubChunkingStrategy()
    line_window_strategy = StubChunkingStrategy()
    resolver = ChunkingStrategyResolver(
        tree_sitter_strategy=tree_sitter_strategy, line_window_strategy=line_window_strategy
    )

    for code_language in ("python", "typescript", "tsx", "javascript"):
        assert resolver.resolve(code_language) is tree_sitter_strategy
    for text_language in ("markdown", "config", "text", "css"):
        assert resolver.resolve(text_language) is line_window_strategy
