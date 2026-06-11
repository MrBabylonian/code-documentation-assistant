import json
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.sse import EventSourceResponse, format_sse_event

from codedoc.domain.chat import ChatTurn
from codedoc.presentation.schemas.question_schemas import AnswerRequest, FileSpanResponse

question_router = APIRouter(prefix="/api/repositories")


@question_router.post("/{repository_id}/answers")
async def stream_answer(
    request: Request, repository_id: str, payload: AnswerRequest
) -> EventSourceResponse:
    container = request.app.state.container
    if container.question_answering_service is None:
        raise HTTPException(status_code=503, detail="answering service not configured")
    history = tuple(
        ChatTurn(role=turn.role, text=turn.text)  # type: ignore[arg-type]
        for turn in payload.history
    )

    async def event_stream() -> AsyncIterator[bytes]:
        async for event in container.question_answering_service.answer_stream(
            repository_id, payload.question, payload.mode, history
        ):
            # fastapi 0.136 only auto-encodes ServerSentEvent when the path operation
            # itself is a generator; with an explicit response we emit wire bytes directly
            yield format_sse_event(data_str=json.dumps(asdict(event)))

    return EventSourceResponse(event_stream())


@question_router.get("/{repository_id}/file-spans")
async def get_file_span(
    request: Request, repository_id: str, file_path: str, start_line: int, end_line: int
) -> FileSpanResponse:
    container = request.app.state.container
    if container.file_content_reader is None:
        raise HTTPException(status_code=503, detail="file reader not configured")
    file_span = await container.file_content_reader.read_span(
        repository_id, file_path, start_line, end_line
    )
    if file_span is None:
        raise HTTPException(status_code=404, detail="file or span not found")
    return FileSpanResponse(
        file_path=file_span.file_path,
        start_line=file_span.start_line,
        end_line=file_span.end_line,
        content=file_span.content,
    )
