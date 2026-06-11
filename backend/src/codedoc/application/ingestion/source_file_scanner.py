import os
from pathlib import Path

from codedoc.domain.source_file import SourceFile

SKIPPED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "target",
        "vendor",
    }
)
SKIPPED_FILE_NAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "uv.lock",
        "poetry.lock",
        "bun.lock",
        "Cargo.lock",
    }
)
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".md": "markdown",
    ".json": "config",
    ".yaml": "config",
    ".yml": "config",
    ".toml": "config",
}
BINARY_SNIFF_LENGTH_BYTES = 8000


class SourceFileScanner:
    def __init__(self, max_file_size_kb: int) -> None:
        self._max_file_size_bytes = max_file_size_kb * 1024

    def scan(self, root_path: Path) -> list[SourceFile]:
        scanned_files: list[SourceFile] = []
        for current_directory, directory_names, file_names in os.walk(root_path):
            directory_names[:] = [
                directory_name
                for directory_name in directory_names
                if directory_name not in SKIPPED_DIRECTORY_NAMES
            ]
            for file_name in sorted(file_names):
                file_path = Path(current_directory) / file_name
                if self._should_skip(file_path):
                    continue
                scanned_files.append(
                    SourceFile(
                        relative_path=file_path.relative_to(root_path).as_posix(),
                        content=file_path.read_text(encoding="utf-8", errors="replace"),
                        language=EXTENSION_TO_LANGUAGE.get(file_path.suffix, "text"),
                    )
                )
        scanned_files.sort(key=lambda source_file: source_file.relative_path)
        return scanned_files

    def _should_skip(self, file_path: Path) -> bool:
        if file_path.name in SKIPPED_FILE_NAMES:
            return True
        if file_path.stat().st_size > self._max_file_size_bytes:
            return True
        with file_path.open("rb") as binary_probe:
            leading_bytes = binary_probe.read(BINARY_SNIFF_LENGTH_BYTES)
        return b"\x00" in leading_bytes
