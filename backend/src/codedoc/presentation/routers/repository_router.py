import asyncio

from fastapi import APIRouter, HTTPException, Request, status

from codedoc.domain.code_repository import build_repository_id
from codedoc.presentation.schemas.repository_schemas import (
    IngestRepositoryRequest,
    IngestRepositoryResponse,
    RepositoryResponse,
)

repository_router = APIRouter(prefix="/api/repositories")


@repository_router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_repository(
    request: Request, payload: IngestRepositoryRequest
) -> IngestRepositoryResponse:
    container = request.app.state.container
    if container.repository_ingestion_service is None:
        raise HTTPException(status_code=503, detail="ingestion service not configured")
    ingestion_task = asyncio.create_task(
        container.repository_ingestion_service.ingest(payload.github_url)
    )
    # the event loop keeps only weak references to tasks — without this strong reference
    # the ingestion task can be garbage-collected mid-run (Python docs, asyncio.create_task)
    request.app.state.ingestion_tasks.add(ingestion_task)
    ingestion_task.add_done_callback(request.app.state.ingestion_tasks.discard)
    return IngestRepositoryResponse(repository_id=build_repository_id(payload.github_url))


@repository_router.get("")
async def list_repositories(request: Request) -> list[RepositoryResponse]:
    repositories = await request.app.state.container.repository_store.list_all()
    return [RepositoryResponse.from_domain(repository) for repository in repositories]


@repository_router.get("/{repository_id}")
async def get_repository(request: Request, repository_id: str) -> RepositoryResponse:
    repository = await request.app.state.container.repository_store.get(repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    return RepositoryResponse.from_domain(repository)
