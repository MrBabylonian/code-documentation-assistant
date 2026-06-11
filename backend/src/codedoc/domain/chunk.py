from dataclasses import dataclass
from enum import StrEnum


class SymbolKind(StrEnum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    TEXT_BLOCK = "text_block"


def build_chunk_id(repository_id: str, file_path: str, start_line: int, end_line: int) -> str:
    return f"{repository_id}:{file_path}:{start_line}-{end_line}"


@dataclass(frozen=True)
class CodeChunk:
    chunk_id: str
    repository_id: str
    file_path: str
    language: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    symbol_name: str | None
    symbol_kind: SymbolKind
    enclosing_scope: str | None
    docstring: str | None
    code: str

    @property
    def composed_embedding_text(self) -> str:
        signature_line = self.code.splitlines()[0] if self.code else ""
        parts = [self.file_path, signature_line, self.docstring or "", self.code]
        return "\n".join(part for part in parts if part)
