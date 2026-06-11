from pathlib import Path

DEFAULT_PROMPTS_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "prompts"


class SystemPromptLoader:
    """Prompts live as versioned files in the repo — reviewable and diffable."""

    def __init__(self, prompts_directory: Path = DEFAULT_PROMPTS_DIRECTORY) -> None:
        self._prompts_directory = prompts_directory

    def load(self, prompt_name: str) -> str:
        return (self._prompts_directory / f"{prompt_name}.md").read_text(encoding="utf-8")
