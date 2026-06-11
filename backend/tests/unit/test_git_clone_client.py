from pathlib import Path

import pytest

from codedoc.domain.errors import CloneError
from codedoc.infrastructure.git.git_clone_client import GitCloneClient
from tests.fixtures.fake_repository_builder import build_local_git_repository


def test_validate_github_url_accepts_and_parses_canonical_forms() -> None:
    client = GitCloneClient(clone_timeout_seconds=120, max_repository_size_mb=200)
    assert client.validate_github_url("https://github.com/owner/repo") == "owner/repo"
    assert client.validate_github_url("https://github.com/owner/repo.git") == "owner/repo"
    assert client.validate_github_url("https://github.com/owner/repo/") == "owner/repo"


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://github.com/owner/repo",  # not https
        "https://gitlab.com/owner/repo",  # wrong host
        "https://github.com/owner",  # missing repo
        "https://github.com/owner/repo/tree/main",  # extra path
        "file:///etc/passwd",  # local scheme
        "git@github.com:owner/repo.git",  # ssh form
    ],
)
def test_validate_github_url_rejects_everything_else(invalid_url: str) -> None:
    client = GitCloneClient(clone_timeout_seconds=120, max_repository_size_mb=200)
    with pytest.raises(CloneError):
        client.validate_github_url(invalid_url)


async def test_clone_shallow_clones_a_local_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin_path = build_local_git_repository(tmp_path, {"src/app.py": "print('hello')\n"})
    client = GitCloneClient(clone_timeout_seconds=120, max_repository_size_mb=200)
    # validation only admits github.com URLs; the subprocess path is exercised via file://,
    # so the validator is bypassed explicitly here (it has its own tests above)
    monkeypatch.setattr(
        GitCloneClient, "validate_github_url", lambda self, github_url: "local/fixture"
    )

    cloned = await client.clone(f"file://{origin_path}", tmp_path / "clone-target")

    assert cloned.name == "local/fixture"
    assert (cloned.clone_path / "src" / "app.py").read_text(encoding="utf-8") == "print('hello')\n"


async def test_clone_times_out_against_a_slow_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slow_git_directory = tmp_path / "bin"
    slow_git_directory.mkdir()
    slow_git_path = slow_git_directory / "git"
    slow_git_path.write_text("#!/bin/sh\nsleep 2\n", encoding="utf-8")
    slow_git_path.chmod(0o755)
    # /bin is included because macOS ships sleep at /bin/sleep, not /usr/bin/sleep
    monkeypatch.setenv("PATH", f"{slow_git_directory}:{Path('/usr/bin')}:{Path('/bin')}")
    monkeypatch.setattr(
        GitCloneClient, "validate_github_url", lambda self, github_url: "local/fixture"
    )
    client = GitCloneClient(clone_timeout_seconds=0.2, max_repository_size_mb=200)

    with pytest.raises(CloneError, match="timed out"):
        await client.clone("https://github.com/owner/repo", tmp_path / "clone-target")


async def test_clone_failure_surfaces_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        GitCloneClient, "validate_github_url", lambda self, github_url: "local/fixture"
    )
    client = GitCloneClient(clone_timeout_seconds=30, max_repository_size_mb=200)

    with pytest.raises(CloneError, match="git clone failed"):
        await client.clone(f"file://{tmp_path / 'does-not-exist'}", tmp_path / "clone-target")


async def test_clone_rejects_oversized_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    two_megabytes_of_text = "x" * (2 * 1024 * 1024)
    origin_path = build_local_git_repository(tmp_path, {"big_file.txt": two_megabytes_of_text})
    monkeypatch.setattr(
        GitCloneClient, "validate_github_url", lambda self, github_url: "local/fixture"
    )
    client = GitCloneClient(clone_timeout_seconds=120, max_repository_size_mb=1)

    with pytest.raises(CloneError, match="exceeds"):
        await client.clone(f"file://{origin_path}", tmp_path / "clone-target")
