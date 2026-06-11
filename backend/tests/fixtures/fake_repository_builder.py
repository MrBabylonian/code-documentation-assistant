import subprocess
from pathlib import Path


def build_local_git_repository(parent_directory: Path, files: dict[str, str]) -> Path:
    """git-init a directory with the given files committed; returns its path (file:// clonable)."""
    repository_path = parent_directory / "fixture-origin"
    repository_path.mkdir()
    for relative_path, content in files.items():
        target_path = repository_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
    git_environment_arguments = ["-c", "user.email=test@example.com", "-c", "user.name=Test"]
    subprocess.run(["git", "init", "--quiet"], cwd=repository_path, check=True)
    subprocess.run(
        ["git", *git_environment_arguments, "add", "-A"], cwd=repository_path, check=True
    )
    subprocess.run(
        ["git", *git_environment_arguments, "commit", "--quiet", "-m", "fixture"],
        cwd=repository_path,
        check=True,
    )
    return repository_path
