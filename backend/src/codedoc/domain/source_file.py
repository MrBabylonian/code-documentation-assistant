from dataclasses import dataclass


@dataclass(frozen=True)
class SourceFile:
    relative_path: str
    content: str
    language: str

    @property
    def line_count(self) -> int:
        return len(self.content.splitlines())
