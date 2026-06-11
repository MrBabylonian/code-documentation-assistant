from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ClonedRepository:
    name: str  # "owner/repo"
    clone_path: Path


class RepositoryCloneClient(Protocol):
    async def clone(self, github_url: str, destination: Path) -> ClonedRepository: ...
