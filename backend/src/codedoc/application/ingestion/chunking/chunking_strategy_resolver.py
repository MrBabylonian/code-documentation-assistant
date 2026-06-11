from codedoc.application.ports.chunking import ChunkingStrategy

LANGUAGES_WITH_SYNTAX_AWARE_CHUNKING = frozenset({"python", "typescript", "tsx", "javascript"})


class ChunkingStrategyResolver:
    def __init__(
        self, tree_sitter_strategy: ChunkingStrategy, line_window_strategy: ChunkingStrategy
    ) -> None:
        self._tree_sitter_strategy = tree_sitter_strategy
        self._line_window_strategy = line_window_strategy

    def resolve(self, language: str) -> ChunkingStrategy:
        if language in LANGUAGES_WITH_SYNTAX_AWARE_CHUNKING:
            return self._tree_sitter_strategy
        return self._line_window_strategy
