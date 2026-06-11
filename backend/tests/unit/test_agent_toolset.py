from codedoc.application.answering.evidence_formatter import EvidenceFormatter
from codedoc.application.ports.indexing import EmbeddedChunk
from codedoc.domain.answer import Citation
from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.source_file import SourceFile
from codedoc.infrastructure.agents.agent_toolset import AgentToolset
from tests.unit.fakes import DeterministicEmbeddings, InMemoryChunkStore, InMemoryFileStore


def _chunk(file_path: str, symbol_name: str, language: str, code: str) -> CodeChunk:
    return CodeChunk(
        chunk_id=build_chunk_id("repo1", file_path, 1, 2), repository_id="repo1",
        file_path=file_path, language=language, start_line=1, end_line=2,
        symbol_name=symbol_name, symbol_kind=SymbolKind.FUNCTION,
        enclosing_scope=None, docstring=None, code=code,
    )


async def _build_toolset() -> AgentToolset:
    chunk_store = InMemoryChunkStore()
    await chunk_store.write_chunks([
        EmbeddedChunk(chunk=_chunk("src/auth.py", "authenticate_user", "python",
                                   "def authenticate_user(): password_check()"), embedding=[0.0]),
        EmbeddedChunk(chunk=_chunk("web/auth.ts", "authenticateUser", "typescript",
                                   "function authenticateUser() { passwordCheck(); }"),
                      embedding=[0.0]),
    ])
    file_store = InMemoryFileStore()
    await file_store.write_files("repo1", [
        SourceFile(relative_path="src/auth.py", content="l1\nl2\nl3", language="python"),
        SourceFile(relative_path="docs/guide.md", content="# guide", language="markdown"),
    ])
    return AgentToolset(
        repository_id="repo1",
        chunk_searcher=chunk_store,
        file_content_reader=file_store,
        embeddings=DeterministicEmbeddings(),
        evidence_formatter=EvidenceFormatter(max_evidence_tokens_per_result=2000),
        search_top_k=5,
    )


async def test_build_tools_exposes_the_four_contract_tools() -> None:
    toolset = await _build_toolset()
    tool_names = [tool.name for tool in toolset.build_tools()]
    assert tool_names == [
        "search_code", "read_file_span", "list_repository_structure", "find_symbol"
    ]
    assert all(tool.description for tool in toolset.build_tools())


async def test_search_code_records_evidence_and_wraps_results() -> None:
    toolset = await _build_toolset()
    search_code_tool = toolset.build_tools()[0]

    tool_output = await search_code_tool.coroutine(query="authenticate password")  # type: ignore[misc]

    assert '<evidence tool="search_code"' in tool_output
    assert Citation(file_path="src/auth.py", start_line=1, end_line=2) in toolset.collected_evidence


async def test_search_code_filters_by_language_and_path_prefix() -> None:
    toolset = await _build_toolset()
    search_code_tool = toolset.build_tools()[0]

    python_only_output = await search_code_tool.coroutine(  # type: ignore[misc]
        query="authenticate", language="python"
    )
    assert "src/auth.py" in python_only_output and "web/auth.ts" not in python_only_output

    web_only_output = await search_code_tool.coroutine(  # type: ignore[misc]
        query="authenticate", path_prefix="web/"
    )
    assert "web/auth.ts" in web_only_output and "src/auth.py" not in web_only_output


async def test_read_file_span_returns_error_string_for_missing_file() -> None:
    toolset = await _build_toolset()
    read_file_span_tool = toolset.build_tools()[1]

    missing_output = await read_file_span_tool.coroutine(  # type: ignore[misc]
        file_path="nope.py", start_line=1, end_line=2
    )
    assert missing_output == "No such file or span in the indexed repository."
    assert toolset.collected_evidence == []

    present_output = await read_file_span_tool.coroutine(  # type: ignore[misc]
        file_path="src/auth.py", start_line=1, end_line=2
    )
    assert '<evidence tool="read_file_span" source="src/auth.py:1-2">' in present_output
    assert Citation(file_path="src/auth.py", start_line=1, end_line=2) in toolset.collected_evidence


async def test_structure_lists_paths_without_recording_evidence() -> None:
    toolset = await _build_toolset()
    structure_tool = toolset.build_tools()[2]

    structure_output = await structure_tool.coroutine()  # type: ignore[misc]

    assert "guide.md" in structure_output and "auth.py" in structure_output
    assert toolset.collected_evidence == []  # structure is orientation, not citable evidence


async def test_find_symbol_records_evidence() -> None:
    toolset = await _build_toolset()
    find_symbol_tool = toolset.build_tools()[3]

    symbol_output = await find_symbol_tool.coroutine(symbol_name="authenticate_user")  # type: ignore[misc]

    assert '<evidence tool="find_symbol"' in symbol_output
    assert Citation(file_path="src/auth.py", start_line=1, end_line=2) in toolset.collected_evidence
