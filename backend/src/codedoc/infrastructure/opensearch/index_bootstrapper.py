from opensearchpy import AsyncOpenSearch

CODE_CHUNKS_INDEX_NAME = "code-chunks"
CODE_FILES_INDEX_NAME = "code-files"
REPOSITORIES_INDEX_NAME = "repositories"
QUERY_TRACES_INDEX_NAME = "query-traces"
HYBRID_SEARCH_PIPELINE_NAME = "hybrid-chunk-search"


class IndexBootstrapper:
    """Creates the four indices and the hybrid search pipeline; idempotent."""

    def __init__(
        self,
        client: AsyncOpenSearch,
        embedding_dimensions: int,
        bm25_weight: float,
        knn_weight: float,
    ) -> None:
        self._client = client
        self._embedding_dimensions = embedding_dimensions
        self._bm25_weight = bm25_weight
        self._knn_weight = knn_weight

    async def bootstrap(self) -> None:
        for index_name, index_body in self._index_definitions().items():
            if not await self._client.indices.exists(index=index_name):
                await self._client.indices.create(index=index_name, body=index_body)
        # search pipeline PUT is idempotent by itself (upsert semantics)
        await self._client.transport.perform_request(
            "PUT",
            f"/_search/pipeline/{HYBRID_SEARCH_PIPELINE_NAME}",
            body={
                "description": (
                    "min-max normalization + weighted arithmetic mean over [bm25, knn]"
                ),
                "phase_results_processors": [
                    {
                        "normalization-processor": {
                            "normalization": {"technique": "min_max"},
                            "combination": {
                                "technique": "arithmetic_mean",
                                # order MUST match the hybrid query's queries array:
                                # [bm25, knn]; weights must sum to exactly 1.0 or
                                # OpenSearch rejects the search
                                "parameters": {
                                    "weights": [self._bm25_weight, self._knn_weight]
                                },
                            },
                        }
                    }
                ],
            },
        )

    def _index_definitions(self) -> dict[str, dict[str, object]]:
        return {
            CODE_CHUNKS_INDEX_NAME: {
                "settings": {"index": {"knn": True}},
                "mappings": {
                    "properties": {
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": self._embedding_dimensions,
                            "method": {
                                "name": "hnsw",
                                "engine": "lucene",
                                "space_type": "cosinesimil",
                            },
                        },
                        "repository_id": {"type": "keyword"},
                        "file_path": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "language": {"type": "keyword"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                        "symbol_name": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "symbol_kind": {"type": "keyword"},
                        "enclosing_scope": {"type": "keyword"},
                        "docstring": {"type": "text"},
                        "code": {"type": "text"},
                    }
                },
            },
            CODE_FILES_INDEX_NAME: {
                "mappings": {
                    "properties": {
                        "repository_id": {"type": "keyword"},
                        "file_path": {"type": "keyword"},
                        "language": {"type": "keyword"},
                        # storage, not search: no inverted index for raw file contents
                        "content": {"type": "text", "index": False},
                    }
                }
            },
            REPOSITORIES_INDEX_NAME: {
                "mappings": {
                    "properties": {
                        "repository_id": {"type": "keyword"},
                        "github_url": {"type": "keyword"},
                        "name": {"type": "keyword"},
                        "status": {"type": "keyword"},
                        "error_message": {"type": "text"},
                        "indexed_file_count": {"type": "integer"},
                        "indexed_chunk_count": {"type": "integer"},
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"},
                    }
                }
            },
            QUERY_TRACES_INDEX_NAME: {
                "mappings": {
                    "dynamic": False,
                    "properties": {
                        "trace_id": {"type": "keyword"},
                        "repository_id": {"type": "keyword"},
                        "question": {"type": "text"},
                        "mode": {"type": "keyword"},
                        "steps": {"type": "object", "enabled": False},
                        "answer_text": {"type": "text", "index": False},
                        "citations": {"type": "object", "enabled": False},
                        "is_grounded": {"type": "boolean"},
                        "input_tokens": {"type": "integer"},
                        "output_tokens": {"type": "integer"},
                        "estimated_cost_usd": {"type": "float"},
                        "latency_ms": {"type": "integer"},
                        "created_at": {"type": "date"},
                    },
                }
            },
        }
