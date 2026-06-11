import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.source_file import SourceFile

PYTHON_LANGUAGE = Language(tree_sitter_python.language())
TYPESCRIPT_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
JAVASCRIPT_LANGUAGE = Language(tree_sitter_javascript.language())

LANGUAGE_BY_NAME: dict[str, Language] = {
    "python": PYTHON_LANGUAGE,
    "typescript": TYPESCRIPT_LANGUAGE,
    "tsx": TSX_LANGUAGE,
    "javascript": JAVASCRIPT_LANGUAGE,
}

PYTHON_SYMBOL_NODE_TYPES = frozenset(
    {"function_definition", "class_definition", "decorated_definition"}
)
TYPESCRIPT_SYMBOL_NODE_TYPES = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "class_declaration",
        "abstract_class_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
        "lexical_declaration",
        "variable_declaration",
    }
)
SYMBOL_KIND_BY_NODE_TYPE = {
    "function_definition": SymbolKind.FUNCTION,
    "function_declaration": SymbolKind.FUNCTION,
    "generator_function_declaration": SymbolKind.FUNCTION,
    "class_definition": SymbolKind.CLASS,
    "class_declaration": SymbolKind.CLASS,
    "abstract_class_declaration": SymbolKind.CLASS,
    "interface_declaration": SymbolKind.INTERFACE,
    "type_alias_declaration": SymbolKind.INTERFACE,
    "enum_declaration": SymbolKind.INTERFACE,
}
MINIMUM_TEXT_BLOCK_LINE_COUNT = 5


class TreeSitterChunkingStrategy:
    """AST-aware chunking: one chunk per function/class; oversized classes split per method."""

    def __init__(self, max_chunk_line_count: int = 200) -> None:
        self._max_chunk_line_count = max_chunk_line_count

    def chunk(self, repository_id: str, source_file: SourceFile) -> list[CodeChunk]:
        language = LANGUAGE_BY_NAME.get(source_file.language)
        if language is None:
            raise ValueError(
                f"no tree-sitter grammar registered for language: {source_file.language}"
            )
        source_bytes = source_file.content.encode("utf-8")
        tree = Parser(language).parse(source_bytes)

        chunks: list[CodeChunk] = []
        covered_line_ranges: list[tuple[int, int]] = []
        for top_level_node in tree.root_node.children:
            for symbol_node in self._unwrap_top_level(top_level_node, source_file.language):
                emitted = self._emit_symbol_chunks(
                    repository_id, source_file, source_bytes, symbol_node
                )
                chunks.extend(emitted)
                if emitted:
                    covered_line_ranges.append(
                        (
                            min(chunk.start_line for chunk in emitted),
                            max(chunk.end_line for chunk in emitted),
                        )
                    )
        chunks.extend(self._leftover_text_blocks(repository_id, source_file, covered_line_ranges))
        return chunks

    def _unwrap_top_level(self, node: Node, language_name: str) -> list[Node]:
        # TS: exported declarations are nested under export_statement — descend or silently
        # miss every exported symbol.
        if node.type == "export_statement":
            return [child for child in node.children if child.type in TYPESCRIPT_SYMBOL_NODE_TYPES]
        symbol_node_types = (
            PYTHON_SYMBOL_NODE_TYPES if language_name == "python" else TYPESCRIPT_SYMBOL_NODE_TYPES
        )
        return [node] if node.type in symbol_node_types else []

    def _emit_symbol_chunks(
        self, repository_id: str, source_file: SourceFile, source_bytes: bytes, symbol_node: Node
    ) -> list[CodeChunk]:
        range_node = symbol_node
        definition_node = symbol_node
        if symbol_node.type == "decorated_definition":
            # decorators are excluded from the inner definition's range; the wrapper includes them
            inner = symbol_node.child_by_field_name("definition") or symbol_node.children[-1]
            definition_node = inner
        if symbol_node.parent is not None and symbol_node.parent.type == "export_statement":
            range_node = symbol_node.parent

        symbol_name = self._symbol_name(definition_node)
        symbol_kind = SYMBOL_KIND_BY_NODE_TYPE.get(definition_node.type, SymbolKind.FUNCTION)
        start_line = range_node.start_point[0] + 1
        end_line = range_node.end_point[0] + 1

        if (
            symbol_kind is SymbolKind.CLASS
            and end_line - start_line + 1 > self._max_chunk_line_count
        ):
            return self._split_class(
                repository_id, source_file, source_bytes, definition_node, symbol_name, start_line
            )

        return [
            self._build_chunk(
                repository_id,
                source_file,
                source_bytes,
                range_node,
                symbol_name,
                symbol_kind,
                enclosing_scope=None,
                docstring=self._python_docstring(
                    definition_node, source_bytes, source_file.language
                ),
            )
        ]

    def _split_class(
        self,
        repository_id: str,
        source_file: SourceFile,
        source_bytes: bytes,
        class_node: Node,
        class_name: str | None,
        class_start_line: int,
    ) -> list[CodeChunk]:
        body_node = class_node.child_by_field_name("body")
        method_nodes = (
            [
                child
                for child in body_node.children
                if child.type
                in {"function_definition", "decorated_definition", "method_definition"}
            ]
            if body_node is not None
            else []
        )
        chunks: list[CodeChunk] = []
        if method_nodes:
            first_method_start_line = min(node.start_point[0] + 1 for node in method_nodes)
            skeleton_lines = source_file.content.splitlines()[
                class_start_line - 1 : first_method_start_line - 1
            ]
            chunks.append(
                CodeChunk(
                    chunk_id=build_chunk_id(
                        repository_id,
                        source_file.relative_path,
                        class_start_line,
                        first_method_start_line - 1,
                    ),
                    repository_id=repository_id,
                    file_path=source_file.relative_path,
                    language=source_file.language,
                    start_line=class_start_line,
                    end_line=first_method_start_line - 1,
                    symbol_name=class_name,
                    symbol_kind=SymbolKind.CLASS,
                    enclosing_scope=None,
                    docstring=self._python_docstring(
                        class_node, source_bytes, source_file.language
                    ),
                    code="\n".join(skeleton_lines).rstrip(),
                )
            )
        for method_node in method_nodes:
            definition_node = method_node
            if method_node.type == "decorated_definition":
                definition_node = (
                    method_node.child_by_field_name("definition") or method_node.children[-1]
                )
            chunks.append(
                self._build_chunk(
                    repository_id,
                    source_file,
                    source_bytes,
                    method_node,
                    self._symbol_name(definition_node),
                    SymbolKind.METHOD,
                    enclosing_scope=class_name,
                    docstring=self._python_docstring(
                        definition_node, source_bytes, source_file.language
                    ),
                )
            )
        return chunks

    def _build_chunk(
        self,
        repository_id: str,
        source_file: SourceFile,
        source_bytes: bytes,
        range_node: Node,
        symbol_name: str | None,
        symbol_kind: SymbolKind,
        enclosing_scope: str | None,
        docstring: str | None,
    ) -> CodeChunk:
        start_line = range_node.start_point[0] + 1
        end_line = range_node.end_point[0] + 1
        return CodeChunk(
            chunk_id=build_chunk_id(repository_id, source_file.relative_path, start_line, end_line),
            repository_id=repository_id,
            file_path=source_file.relative_path,
            language=source_file.language,
            start_line=start_line,
            end_line=end_line,
            symbol_name=symbol_name,
            symbol_kind=symbol_kind,
            enclosing_scope=enclosing_scope,
            docstring=docstring,
            # slice the ORIGINAL bytes — byte offsets are not str offsets with non-ASCII source
            code=source_bytes[range_node.start_byte : range_node.end_byte].decode(
                "utf-8", errors="replace"
            ),
        )

    def _symbol_name(self, definition_node: Node) -> str | None:
        name_node = definition_node.child_by_field_name("name")
        if name_node is not None and name_node.text is not None:
            return name_node.text.decode("utf-8")
        if definition_node.type in {"lexical_declaration", "variable_declaration"}:
            for declarator_node in definition_node.children:
                if declarator_node.type == "variable_declarator":
                    value_node = declarator_node.child_by_field_name("value")
                    declared_name_node = declarator_node.child_by_field_name("name")
                    if (
                        value_node is not None
                        and value_node.type in {"arrow_function", "function_expression"}
                        and declared_name_node is not None
                        and declared_name_node.text is not None
                    ):
                        return declared_name_node.text.decode("utf-8")
        return None

    def _python_docstring(
        self, definition_node: Node, source_bytes: bytes, language_name: str
    ) -> str | None:
        if language_name != "python":
            return None
        body_node = definition_node.child_by_field_name("body")
        if body_node is None or not body_node.children:
            return None
        first_statement = body_node.children[0]
        if first_statement.type != "expression_statement" or not first_statement.children:
            return None
        string_node = first_statement.children[0]
        if string_node.type != "string":
            return None
        raw_text = source_bytes[string_node.start_byte : string_node.end_byte].decode(
            "utf-8", errors="replace"
        )
        return raw_text.strip("\"' \n")

    def _leftover_text_blocks(
        self,
        repository_id: str,
        source_file: SourceFile,
        covered_line_ranges: list[tuple[int, int]],
    ) -> list[CodeChunk]:
        content_lines = source_file.content.splitlines()
        is_line_covered = [False] * (len(content_lines) + 1)
        for range_start, range_end in covered_line_ranges:
            for line_number in range(range_start, min(range_end, len(content_lines)) + 1):
                is_line_covered[line_number] = True

        text_blocks: list[CodeChunk] = []
        block_start: int | None = None
        for line_number in range(1, len(content_lines) + 2):
            line_is_uncovered = (
                line_number <= len(content_lines) and not is_line_covered[line_number]
            )
            if line_is_uncovered and block_start is None:
                block_start = line_number
            elif not line_is_uncovered and block_start is not None:
                trimmed = self._trim_blank_edges(content_lines, block_start, line_number - 1)
                if (
                    trimmed is not None
                    and trimmed[1] - trimmed[0] + 1 > MINIMUM_TEXT_BLOCK_LINE_COUNT
                ):
                    trimmed_start, trimmed_end = trimmed
                    text_blocks.append(
                        CodeChunk(
                            chunk_id=build_chunk_id(
                                repository_id, source_file.relative_path, trimmed_start, trimmed_end
                            ),
                            repository_id=repository_id,
                            file_path=source_file.relative_path,
                            language=source_file.language,
                            start_line=trimmed_start,
                            end_line=trimmed_end,
                            symbol_name=None,
                            symbol_kind=SymbolKind.TEXT_BLOCK,
                            enclosing_scope=None,
                            docstring=None,
                            code="\n".join(content_lines[trimmed_start - 1 : trimmed_end]),
                        )
                    )
                block_start = None
        return text_blocks

    @staticmethod
    def _trim_blank_edges(
        content_lines: list[str], start_line: int, end_line: int
    ) -> tuple[int, int] | None:
        while start_line <= end_line and not content_lines[start_line - 1].strip():
            start_line += 1
        while end_line >= start_line and not content_lines[end_line - 1].strip():
            end_line -= 1
        return (start_line, end_line) if start_line <= end_line else None
