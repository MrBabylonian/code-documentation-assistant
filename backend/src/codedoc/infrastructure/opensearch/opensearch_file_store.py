from collections.abc import Sequence

from opensearchpy import AsyncOpenSearch, NotFoundError
from opensearchpy.helpers import async_bulk

from codedoc.application.ports.searching import FileSpan
from codedoc.domain.source_file import SourceFile
from codedoc.infrastructure.opensearch.index_bootstrapper import CODE_FILES_INDEX_NAME

LIST_PATHS_RESULT_LIMIT = 10_000


class OpensearchFileStore:
    """Implements FileContentWriter + FileContentReader over the code-files index."""

    def __init__(self, client: AsyncOpenSearch) -> None:
        self._client = client

    async def write_files(self, repository_id: str, source_files: Sequence[SourceFile]) -> None:
        bulk_actions = [
            {
                "_index": CODE_FILES_INDEX_NAME,
                "_id": f"{repository_id}:{source_file.relative_path}",
                "_source": {
                    "repository_id": repository_id,
                    "file_path": source_file.relative_path,
                    "language": source_file.language,
                    "content": source_file.content,
                },
            }
            for source_file in source_files
        ]
        await async_bulk(self._client, bulk_actions)
        await self._client.indices.refresh(index=CODE_FILES_INDEX_NAME)

    async def delete_repository_files(self, repository_id: str) -> None:
        await self._client.delete_by_query(
            index=CODE_FILES_INDEX_NAME,
            body={"query": {"term": {"repository_id": repository_id}}},
            params={"refresh": "true"},
        )

    async def read_span(
        self, repository_id: str, file_path: str, start_line: int, end_line: int
    ) -> FileSpan | None:
        try:
            document = await self._client.get(
                index=CODE_FILES_INDEX_NAME, id=f"{repository_id}:{file_path}"
            )
        except NotFoundError:
            # absence is a legitimate answer here, not an error to propagate
            return None
        content_lines = str(document["_source"]["content"]).splitlines()
        clamped_start = max(1, start_line)
        clamped_end = min(len(content_lines), end_line)
        if clamped_start > clamped_end:
            return None
        return FileSpan(
            file_path=file_path,
            start_line=clamped_start,
            end_line=clamped_end,
            content="\n".join(content_lines[clamped_start - 1 : clamped_end]),
        )

    async def list_paths(self, repository_id: str, path_prefix: str | None) -> list[str]:
        filter_clauses: list[dict[str, object]] = [{"term": {"repository_id": repository_id}}]
        if path_prefix is not None:
            filter_clauses.append({"prefix": {"file_path": path_prefix}})
        search_response = await self._client.search(
            index=CODE_FILES_INDEX_NAME,
            body={
                "size": LIST_PATHS_RESULT_LIMIT,
                "_source": ["file_path"],
                "query": {"bool": {"filter": filter_clauses}},
            },
        )
        return sorted(str(hit["_source"]["file_path"]) for hit in search_response["hits"]["hits"])
