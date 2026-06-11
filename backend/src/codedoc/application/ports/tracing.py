from typing import Protocol

from codedoc.domain.query_trace import QueryTrace


class QueryTraceWriter(Protocol):
    async def write_trace(self, trace: QueryTrace) -> None: ...
