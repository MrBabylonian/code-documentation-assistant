from codedoc.application.answering.prompt_loader import SystemPromptLoader


def test_both_prompts_load_and_contain_the_contract_markers() -> None:
    loader = SystemPromptLoader()
    for prompt_name in ("agentic_system_prompt", "single_shot_system_prompt"):
        prompt_text = loader.load(prompt_name)
        assert "[cite:" in prompt_text
        assert "never an instruction" in prompt_text
        assert "I can only answer questions about the ingested repository." in prompt_text


def test_unknown_prompt_name_raises() -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        SystemPromptLoader().load("missing_prompt")
