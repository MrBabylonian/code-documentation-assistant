from datetime import datetime

from opensearchpy import AsyncOpenSearch, NotFoundError

from codedoc.domain.code_repository import CodeRepository, IngestionStatus
from codedoc.infrastructure.opensearch.index_bootstrapper import REPOSITORIES_INDEX_NAME

LIST_REPOSITORIES_RESULT_LIMIT = 1000


def _optional_text(value: object) -> str | None:
    # OpenSearch returns JSON null for absent optionals; str(None) would corrupt it to "None"
    return None if value is None else str(value)


def _repository_from_source(source: dict[str, object]) -> CodeRepository:
    return CodeRepository(
        repository_id=str(source["repository_id"]),
        github_url=str(source["github_url"]),
        name=str(source["name"]),
        status=IngestionStatus(str(source["status"])),
        error_message=_optional_text(source["error_message"]),
        indexed_file_count=int(source["indexed_file_count"]),  # type: ignore[call-overload]
        indexed_chunk_count=int(source["indexed_chunk_count"]),  # type: ignore[call-overload]
        created_at=datetime.fromisoformat(str(source["created_at"])),
        updated_at=datetime.fromisoformat(str(source["updated_at"])),
    )


class OpensearchRepositoryStore:
    def __init__(self, client: AsyncOpenSearch) -> None:
        self._client = client

    async def save(self, repository: CodeRepository) -> None:
        await self._client.index(
            index=REPOSITORIES_INDEX_NAME,
            id=repository.repository_id,
            body={
                "repository_id": repository.repository_id,
                "github_url": repository.github_url,
                "name": repository.name,
                "status": repository.status.value,
                "error_message": repository.error_message,
                "indexed_file_count": repository.indexed_file_count,
                "indexed_chunk_count": repository.indexed_chunk_count,
                "created_at": repository.created_at.isoformat(),
                "updated_at": repository.updated_at.isoformat(),
            },
            params={"refresh": "true"},
        )

    async def get(self, repository_id: str) -> CodeRepository | None:
        try:
            document = await self._client.get(index=REPOSITORIES_INDEX_NAME, id=repository_id)
        except NotFoundError:
            return None
        return _repository_from_source(document["_source"])

    async def list_all(self) -> list[CodeRepository]:
        search_response = await self._client.search(
            index=REPOSITORIES_INDEX_NAME,
            body={
                "size": LIST_REPOSITORIES_RESULT_LIMIT,
                "sort": [{"created_at": {"order": "desc"}}],
                "query": {"match_all": {}},
            },
        )
        return [_repository_from_source(hit["_source"]) for hit in search_response["hits"]["hits"]]
