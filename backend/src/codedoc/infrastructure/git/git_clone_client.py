import asyncio
import re
from pathlib import Path

from codedoc.application.ports.cloning import ClonedRepository
from codedoc.domain.errors import CloneError

GITHUB_URL_PATTERN = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
STDERR_TAIL_LENGTH_CHARS = 500


class GitCloneClient:
    """Shallow-clones public GitHub repositories with timeout and size caps.

    Clone content is untrusted input: it is only ever read, never executed.
    """

    def __init__(self, clone_timeout_seconds: float, max_repository_size_mb: int) -> None:
        self._clone_timeout_seconds = clone_timeout_seconds
        self._max_repository_size_bytes = max_repository_size_mb * 1024 * 1024

    def validate_github_url(self, github_url: str) -> str:
        url_match = GITHUB_URL_PATTERN.match(github_url.strip())
        if url_match is None:
            raise CloneError(f"not a public github.com repository URL: {github_url}")
        return f"{url_match.group(1)}/{url_match.group(2)}"

    async def clone(self, github_url: str, destination: Path) -> ClonedRepository:
        repository_name = self.validate_github_url(github_url)
        clone_process = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            "--single-branch",
            github_url,
            str(destination),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            unused_stdout, stderr_bytes = await asyncio.wait_for(
                clone_process.communicate(), timeout=self._clone_timeout_seconds
            )
        except TimeoutError as timeout_error:
            clone_process.kill()
            await clone_process.communicate()
            raise CloneError(
                f"clone timed out after {self._clone_timeout_seconds}s: {github_url}"
            ) from timeout_error
        if clone_process.returncode != 0:
            stderr_tail = stderr_bytes.decode("utf-8", errors="replace")[-STDERR_TAIL_LENGTH_CHARS:]
            raise CloneError(f"git clone failed: {stderr_tail}")
        self._enforce_size_cap(destination)
        return ClonedRepository(name=repository_name, clone_path=destination)

    def _enforce_size_cap(self, clone_path: Path) -> None:
        total_size_bytes = sum(
            file_path.stat().st_size
            for file_path in clone_path.rglob("*")
            if file_path.is_file() and ".git" not in file_path.parts
        )
        if total_size_bytes > self._max_repository_size_bytes:
            raise CloneError(
                f"repository exceeds the size cap: {total_size_bytes} bytes "
                f"> {self._max_repository_size_bytes} bytes"
            )
