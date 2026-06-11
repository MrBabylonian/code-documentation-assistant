import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from codedoc.infrastructure.openai.retrying_embeddings import RetryingEmbeddings
from tests.unit.fakes import DeterministicEmbeddings


def _status_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    response = httpx.Response(status_code, request=request)
    return APIStatusError("boom", response=response, body=None)


class FlakyEmbeddings(DeterministicEmbeddings):
    """Fails the first N calls with the given error, then behaves normally."""

    def __init__(self, failures_before_success: int, error: Exception) -> None:
        super().__init__(dimension=8)
        self.remaining_failures = failures_before_success
        self.call_count = 0
        self._error = error

    async def aembed_query(self, text: str) -> list[float]:
        self.call_count += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise self._error
        return await super().aembed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise self._error
        return await super().aembed_documents(texts)


async def test_retries_transient_status_errors_and_succeeds() -> None:
    flaky_inner = FlakyEmbeddings(failures_before_success=2, error=_status_error(431))
    embeddings = RetryingEmbeddings(flaky_inner, max_attempts=3, backoff_seconds=0.0)

    vector = await embeddings.aembed_query("hello")

    assert len(vector) == 8
    assert flaky_inner.call_count == 3


async def test_gives_up_after_max_attempts() -> None:
    flaky_inner = FlakyEmbeddings(failures_before_success=99, error=_status_error(431))
    embeddings = RetryingEmbeddings(flaky_inner, max_attempts=3, backoff_seconds=0.0)

    with pytest.raises(APIStatusError):
        await embeddings.aembed_query("hello")
    assert flaky_inner.call_count == 3


async def test_does_not_retry_genuine_client_errors() -> None:
    flaky_inner = FlakyEmbeddings(failures_before_success=99, error=_status_error(401))
    embeddings = RetryingEmbeddings(flaky_inner, max_attempts=3, backoff_seconds=0.0)

    with pytest.raises(APIStatusError):
        await embeddings.aembed_query("hello")
    assert flaky_inner.call_count == 1  # 401 is not transient — no retry


async def test_retries_connection_errors_on_batch_embedding() -> None:
    connection_error = APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    )
    flaky_inner = FlakyEmbeddings(failures_before_success=1, error=connection_error)
    embeddings = RetryingEmbeddings(flaky_inner, max_attempts=3, backoff_seconds=0.0)

    vectors = await embeddings.aembed_documents(["alpha", "beta"])

    assert len(vectors) == 2
    assert flaky_inner.call_count == 2


def test_sync_methods_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    embeddings = RetryingEmbeddings(DeterministicEmbeddings(dimension=8), max_attempts=2)
    assert len(embeddings.embed_query("hello")) == 8
    assert len(embeddings.embed_documents(["alpha"])) == 1
