from datetime import UTC, datetime

from codedoc.domain.chat import AnswerMode
from codedoc.domain.chunk import CodeChunk, SymbolKind, build_chunk_id
from codedoc.domain.code_repository import CodeRepository, IngestionStatus, build_repository_id
from codedoc.domain.source_file import SourceFile
from codedoc.domain.streaming import AnswerTokenEvent, ToolCallEvent


def test_build_repository_id_normalizes_equivalent_urls() -> None:
    plain_id = build_repository_id("https://github.com/Owner/Repo")
    assert plain_id == build_repository_id("https://github.com/Owner/Repo.git")
    assert plain_id == build_repository_id("https://github.com/Owner/Repo/")
    assert len(plain_id) == 12
    assert plain_id != build_repository_id("https://github.com/Owner/OtherRepo")


def test_chunk_id_format_and_composed_embedding_text() -> None:
    chunk = CodeChunk(
        chunk_id=build_chunk_id("abc123def456", "src/auth/login.py", 10, 42),
        repository_id="abc123def456",
        file_path="src/auth/login.py",
        language="python",
        start_line=10,
        end_line=42,
        symbol_name="authenticate_user",
        symbol_kind=SymbolKind.FUNCTION,
        enclosing_scope=None,
        docstring="Validates credentials.",
        code="def authenticate_user(credentials):\n    return check(credentials)",
    )
    assert chunk.chunk_id == "abc123def456:src/auth/login.py:10-42"
    composed_text = chunk.composed_embedding_text
    assert composed_text.splitlines()[0] == "src/auth/login.py"
    assert "def authenticate_user(credentials):" in composed_text
    assert "Validates credentials." in composed_text
    # docstring appears before the code body
    assert composed_text.index("Validates credentials.") < composed_text.index("return check")


def test_composed_embedding_text_skips_missing_docstring() -> None:
    chunk = CodeChunk(
        chunk_id="abc:path.py:1-2",
        repository_id="abc",
        file_path="path.py",
        language="python",
        start_line=1,
        end_line=2,
        symbol_name=None,
        symbol_kind=SymbolKind.TEXT_BLOCK,
        enclosing_scope=None,
        docstring=None,
        code="VALUE = 1\nOTHER = 2",
    )
    assert "\n\n" not in chunk.composed_embedding_text


def test_source_file_line_count() -> None:
    source_file = SourceFile(relative_path="a.py", content="one\ntwo\nthree", language="python")
    assert source_file.line_count == 3


def test_stream_events_carry_kind_discriminators_by_default() -> None:
    assert ToolCallEvent(tool_name="search_code", arguments={"query": "auth"}).kind == "tool_call"
    assert AnswerTokenEvent(text="hello").kind == "answer_token"


def test_repository_status_lifecycle_values() -> None:
    assert [status.value for status in IngestionStatus] == [
        "pending",
        "cloning",
        "parsing",
        "embedding",
        "indexing",
        "ready",
        "failed",
    ]
    repository = CodeRepository(
        repository_id="abc123def456",
        github_url="https://github.com/owner/repo",
        name="owner/repo",
        status=IngestionStatus.PENDING,
        error_message=None,
        indexed_file_count=0,
        indexed_chunk_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert repository.status is IngestionStatus.PENDING
    assert AnswerMode("agentic") is AnswerMode.AGENTIC
