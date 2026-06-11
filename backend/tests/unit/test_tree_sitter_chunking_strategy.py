from pathlib import Path

import pytest

from codedoc.application.ingestion.chunking.tree_sitter_chunking_strategy import (
    TreeSitterChunkingStrategy,
)
from codedoc.domain.chunk import CodeChunk, SymbolKind
from codedoc.domain.source_file import SourceFile

FIXTURES_DIRECTORY = Path(__file__).parent.parent / "fixtures"


def _chunk_fixture(
    fixture_name: str, language: str, max_chunk_line_count: int = 200
) -> list[CodeChunk]:
    source_file = SourceFile(
        relative_path=fixture_name,
        content=(FIXTURES_DIRECTORY / fixture_name).read_text(encoding="utf-8"),
        language=language,
    )
    strategy = TreeSitterChunkingStrategy(max_chunk_line_count=max_chunk_line_count)
    return sorted(strategy.chunk("repo1", source_file), key=lambda chunk: chunk.start_line)


def test_python_symbols_with_decorator_ranges_and_docstrings() -> None:
    chunks = _chunk_fixture("sample_module.py", "python")

    expected_summary = [
        (None, SymbolKind.TEXT_BLOCK, 1, 9),
        ("decorated_function", SymbolKind.FUNCTION, 12, 15),
        ("SampleService", SymbolKind.CLASS, 18, 26),
        ("async_function", SymbolKind.FUNCTION, 29, 31),
    ]
    actual_summary = [
        (chunk.symbol_name, chunk.symbol_kind, chunk.start_line, chunk.end_line) for chunk in chunks
    ]
    assert actual_summary == expected_summary

    decorated_chunk = chunks[1]
    assert decorated_chunk.docstring == "Decorated function docstring."
    assert decorated_chunk.code.startswith("@sample_decorator")
    assert chunks[2].docstring == "Service docstring."


def test_python_oversized_class_splits_into_methods_with_enclosing_scope() -> None:
    chunks = _chunk_fixture("sample_module.py", "python", max_chunk_line_count=8)

    class_related_chunks = [
        chunk for chunk in chunks if chunk.start_line >= 18 and chunk.end_line <= 26
    ]
    summary = [
        (
            chunk.symbol_name,
            chunk.symbol_kind,
            chunk.start_line,
            chunk.end_line,
            chunk.enclosing_scope,
        )
        for chunk in class_related_chunks
    ]
    assert ("SampleService", SymbolKind.CLASS, 18, 20, None) in summary
    assert ("first_method", SymbolKind.METHOD, 21, 23, "SampleService") in summary
    assert ("second_method", SymbolKind.METHOD, 25, 26, "SampleService") in summary
    method_chunk = next(
        chunk for chunk in class_related_chunks if chunk.symbol_name == "first_method"
    )
    assert method_chunk.docstring == "First method docstring."


def test_typescript_symbols_including_exports_interfaces_and_arrow_functions() -> None:
    chunks = _chunk_fixture("sample_component.ts", "typescript")

    expected_summary = [
        ("exportedFunction", SymbolKind.FUNCTION, 1, 3),
        ("ExportedService", SymbolKind.CLASS, 5, 9),
        ("LocalShape", SymbolKind.INTERFACE, 11, 13),
        ("arrowHandler", SymbolKind.FUNCTION, 15, 17),
        ("functionExpressionHandler", SymbolKind.FUNCTION, 19, 21),
    ]
    actual_summary = [
        (chunk.symbol_name, chunk.symbol_kind, chunk.start_line, chunk.end_line) for chunk in chunks
    ]
    assert actual_summary == expected_summary


def test_chunk_ids_and_repository_id_are_populated() -> None:
    chunks = _chunk_fixture("sample_component.ts", "typescript")
    first_chunk = chunks[0]
    assert first_chunk.repository_id == "repo1"
    assert first_chunk.chunk_id == "repo1:sample_component.ts:1-3"
    assert first_chunk.language == "typescript"


def test_unsupported_language_raises() -> None:
    strategy = TreeSitterChunkingStrategy()
    source_file = SourceFile(relative_path="style.css", content="body {}", language="css")
    with pytest.raises(ValueError, match="css"):
        strategy.chunk("repo1", source_file)
