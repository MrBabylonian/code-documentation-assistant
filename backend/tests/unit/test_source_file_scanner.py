from pathlib import Path

from codedoc.application.ingestion.source_file_scanner import SourceFileScanner


def _write(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def test_scanner_collects_source_files_with_posix_relative_paths_and_languages(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "src" / "app.py", "print('hello')\n")
    _write(tmp_path / "web" / "index.ts", "export const value = 1;\n")
    _write(tmp_path / "README.md", "# Title\n")

    scanned_files = SourceFileScanner(max_file_size_kb=512).scan(tmp_path)

    by_path = {source_file.relative_path: source_file for source_file in scanned_files}
    assert set(by_path) == {"src/app.py", "web/index.ts", "README.md"}
    assert by_path["src/app.py"].language == "python"
    assert by_path["web/index.ts"].language == "typescript"
    assert by_path["README.md"].language == "markdown"


def test_scanner_skips_vendored_dirs_lockfiles_binaries_and_oversized_files(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "node_modules" / "pkg" / "index.js", "ignored")
    _write(tmp_path / ".git" / "config", "ignored")
    _write(tmp_path / "package-lock.json", "{}")
    _write(tmp_path / "src" / "kept.py", "kept = True\n")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\x00\x1a binary")
    (tmp_path / "src" / "huge.py").write_text("x = 1\n" * 200_000, encoding="utf-8")

    scanned_files = SourceFileScanner(max_file_size_kb=512).scan(tmp_path)

    assert [source_file.relative_path for source_file in scanned_files] == ["src/kept.py"]


def test_scanner_tags_unknown_text_extensions_as_text(tmp_path: Path) -> None:
    _write(tmp_path / "Makefile", "build:\n\techo ok\n")
    _write(tmp_path / "settings.toml", "[tool]\n")

    scanned_files = SourceFileScanner(max_file_size_kb=512).scan(tmp_path)

    by_path = {source_file.relative_path: source_file.language for source_file in scanned_files}
    assert by_path == {"Makefile": "text", "settings.toml": "config"}
