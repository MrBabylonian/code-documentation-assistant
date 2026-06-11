from collections.abc import Sequence

from opensearchpy import AsyncOpenSearch
from opensearchpy.helpers import async_bulk

from codedoc.application.ports.indexing import EmbeddedChunk
from codedoc.application.ports.searching import ChunkSearchHit
from codedoc.domain.chunk import CodeChunk, SymbolKind
from codedoc.infrastructure.opensearch.index_bootstrapper import (
    CODE_CHUNKS_INDEX_NAME,
    HYBRID_SEARCH_PIPELINE_NAME,
)

FIND_BY_SYMBOL_RESULT_LIMIT = 50


def _optional_text(value: object) -> str | None:
    # OpenSearch returns JSON null for absent optionals; str(None) would corrupt it to "None"
    return None if value is None else str(value)


def _chunk_from_source(source: dict[str, object]) -> CodeChunk:
    return CodeChunk(
        chunk_id=str(source["chunk_id"]),
        repository_id=str(source["repository_id"]),
        file_path=str(source["file_path"]),
        language=str(source["language"]),
        start_line=int(source["start_line"]),  # type: ignore[call-overload]
        end_line=int(source["end_line"]),  # type: ignore[call-overload]
        symbol_name=_optional_text(source["symbol_name"]),
        symbol_kind=SymbolKind(str(source["symbol_kind"])),
        enclosing_scope=_optional_text(source["enclosing_scope"]),
        docstring=_optional_text(source["docstring"]),
        code=str(source["code"]),
    )


class OpensearchChunkRepository:
    """Implements ChunkIndexWriter + ChunkSearcher over the code-chunks index."""

    def __init__(self, client: AsyncOpenSearch) -> None:
        self._client = client

    async def write_chunks(self, embedded_chunks: Sequence[EmbeddedChunk]) -> None:
        bulk_actions = [
            {
                "_index": CODE_CHUNKS_INDEX_NAME,
                "_id": embedded_chunk.chunk.chunk_id,
                "_source": {
                    "chunk_id": embedded_chunk.chunk.chunk_id,
                    "repository_id": embedded_chunk.chunk.repository_id,
                    "file_path": embedded_chunk.chunk.file_path,
                    "language": embedded_chunk.chunk.language,
                    "start_line": embedded_chunk.chunk.start_line,
                    "end_line": embedded_chunk.chunk.end_line,
                    "symbol_name": embedded_chunk.chunk.symbol_name,
                    "symbol_kind": embedded_chunk.chunk.symbol_kind.value,
                    "enclosing_scope": embedded_chunk.chunk.enclosing_scope,
                    "docstring": embedded_chunk.chunk.docstring,
                    "code": embedded_chunk.chunk.code,
                    "embedding": embedded_chunk.embedding,
                },
            }
            for embedded_chunk in embedded_chunks
        ]
        await async_bulk(self._client, bulk_actions)
        await self._client.indices.refresh(index=CODE_CHUNKS_INDEX_NAME)

    async def delete_repository_chunks(self, repository_id: str) -> None:
        await self._client.delete_by_query(
            index=CODE_CHUNKS_INDEX_NAME,
            body={"query": {"term": {"repository_id": repository_id}}},
            params={"refresh": "true"},
        )

    async def search(
        self, repository_id: str, query_text: str, query_embedding: list[float], top_k: int
    ) -> list[ChunkSearchHit]:
        bm25_clause: dict[str, object] = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["symbol_name^3", "file_path^2", "code", "docstring"],
                        }
                    }
                ],
                "filter": [{"term": {"repository_id": repository_id}}],
            }
        }
        knn_clause: dict[str, object] = {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": top_k,
                    # lucene engine supports efficient pre-filtering inside knn
                    "filter": {"term": {"repository_id": repository_id}},
                }
            }
        }
        search_response = await self._client.search(
            index=CODE_CHUNKS_INDEX_NAME,
            params={"search_pipeline": HYBRID_SEARCH_PIPELINE_NAME},
            body={
                "size": top_k,
                "_source": {"excludes": ["embedding"]},
                # clause order [bm25, knn] must match the pipeline's weights order
                "query": {"hybrid": {"queries": [bm25_clause, knn_clause]}},
            },
        )
        return [
            ChunkSearchHit(chunk=_chunk_from_source(hit["_source"]), score=float(hit["_score"]))
            for hit in search_response["hits"]["hits"]
        ]

    async def find_by_symbol(self, repository_id: str, symbol_name: str) -> list[CodeChunk]:
        search_response = await self._client.search(
            index=CODE_CHUNKS_INDEX_NAME,
            body={
                "size": FIND_BY_SYMBOL_RESULT_LIMIT,
                "_source": {"excludes": ["embedding"]},
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"repository_id": repository_id}},
                            {"term": {"symbol_name.keyword": symbol_name}},
                        ]
                    }
                },
            },
        )
        return [_chunk_from_source(hit["_source"]) for hit in search_response["hits"]["hits"]]
