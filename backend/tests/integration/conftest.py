import os
from collections.abc import AsyncIterator

import pytest
from opensearchpy import AsyncOpenSearch

from codedoc.infrastructure.opensearch.index_bootstrapper import IndexBootstrapper

EMBEDDING_DIMENSIONS_FOR_TESTS = 3072  # must match the production mapping — index names are shared


@pytest.fixture
async def opensearch_client() -> AsyncIterator[AsyncOpenSearch]:
    opensearch_url = os.environ.get("CODEDOC_OPENSEARCH_URL", "http://localhost:9200")
    client = AsyncOpenSearch(hosts=[opensearch_url])
    yield client
    # close() is a coroutine in opensearch-py 3.x — forgetting await leaks the aiohttp session
    await client.close()


@pytest.fixture
async def bootstrapped_client(opensearch_client: AsyncOpenSearch) -> AsyncOpenSearch:
    bootstrapper = IndexBootstrapper(
        opensearch_client,
        embedding_dimensions=EMBEDDING_DIMENSIONS_FOR_TESTS,
        bm25_weight=0.3,
        knn_weight=0.7,
    )
    await bootstrapper.bootstrap()
    return opensearch_client
