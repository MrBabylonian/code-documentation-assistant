from dataclasses import asdict

from opensearchpy import AsyncOpenSearch

from codedoc.domain.query_trace import QueryTrace
from codedoc.infrastructure.opensearch.index_bootstrapper import QUERY_TRACES_INDEX_NAME


class OpensearchQueryTraceWriter:
    def __init__(self, client: AsyncOpenSearch) -> None:
        self._client = client

    async def write_trace(self, trace: QueryTrace) -> None:
        trace_document = asdict(trace)
        trace_document["mode"] = trace.mode.value
        trace_document["created_at"] = trace.created_at.isoformat()
        await self._client.index(
            index=QUERY_TRACES_INDEX_NAME, id=trace.trace_id, body=trace_document
        )
