import asyncio
from collections.abc import Awaitable, Callable

import structlog
from langchain_core.embeddings import Embeddings
from openai import APIConnectionError, APIStatusError, APITimeoutError

logger = structlog.get_logger()

# 431 ("request headers too large") is returned intermittently by OpenAI's edge and
# succeeds on retry — observed twice in this project's first ~60 real calls. The SDK
# only auto-retries 408/429/5xx, so it needs handling here.
TRANSIENT_STATUS_CODES = frozenset({431, 500, 502, 503, 504})


def _is_transient(error: Exception) -> bool:
    if isinstance(error, APIStatusError):
        return error.status_code in TRANSIENT_STATUS_CODES
    return isinstance(error, APIConnectionError | APITimeoutError)


class RetryingEmbeddings(Embeddings):
    """Decorator over any Embeddings: retries transient provider errors with backoff."""

    def __init__(
        self, inner: Embeddings, max_attempts: int = 3, backoff_seconds: float = 1.0
    ) -> None:
        self._inner = inner
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        async def attempt_embedding() -> list[list[float]]:
            return await self._inner.aembed_documents(texts)

        return await self._retry(attempt_embedding, operation_name="aembed_documents")

    async def aembed_query(self, text: str) -> list[float]:
        async def attempt_embedding() -> list[float]:
            return await self._inner.aembed_query(text)

        return await self._retry(attempt_embedding, operation_name="aembed_query")

    async def _retry[ResultT](
        self, attempt: Callable[[], Awaitable[ResultT]], operation_name: str
    ) -> ResultT:
        for attempt_number in range(1, self._max_attempts + 1):
            try:
                return await attempt()
            except Exception as embedding_error:  # noqa: BLE001
                if not _is_transient(embedding_error) or attempt_number == self._max_attempts:
                    raise
                logger.warning(
                    "embedding_retry",
                    operation=operation_name,
                    attempt=attempt_number,
                    error=str(embedding_error),
                )
                await asyncio.sleep(self._backoff_seconds * attempt_number)
        raise AssertionError("unreachable: loop either returns or raises")
