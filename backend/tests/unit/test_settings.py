import pytest
from pydantic import ValidationError


def test_settings_read_defaults_and_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEDOC_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CODEDOC_SEARCH_TOP_K", "13")
    from codedoc.settings import AppSettings

    # pyright lacks mypy's pydantic-settings plugin: openai_api_key arrives from the env
    settings = AppSettings()  # pyright: ignore[reportCallIssue]
    assert settings.openai_api_key == "test-key"
    assert settings.search_top_k == 13
    assert settings.opensearch_url == "http://localhost:9200"
    assert settings.chat_model_name == "gpt-5.4-mini"
    assert settings.embedding_model_name == "text-embedding-3-large"
    assert settings.embedding_dimensions == 3072
    assert settings.knn_weight + settings.bm25_weight == pytest.approx(1.0)


def test_settings_require_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEDOC_OPENAI_API_KEY", raising=False)
    from codedoc.settings import AppSettings

    with pytest.raises(ValidationError):
        # the missing-key failure is the point of the test; _env_file is a dynamic kwarg
        AppSettings(_env_file=None)  # pyright: ignore[reportCallIssue]
