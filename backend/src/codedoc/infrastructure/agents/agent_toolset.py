from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool, StructuredTool

from codedoc.application.answering.evidence_formatter import EvidenceFormatter
from codedoc.application.ports.searching import ChunkSearcher, FileContentReader
from codedoc.domain.answer import Citation
from codedoc.domain.chunk import CodeChunk

MISSING_SPAN_MESSAGE = "No such file or span in the indexed repository."
EMPTY_RESULT_MESSAGE = "No results. Try different terms, or list_repository_structure to orient."


class AgentToolset:
    """Builds the agent's four read-only tools and records every span shown to the model.

    One instance PER REQUEST: collected_evidence is the grounding set for citation
    validation. Read-only by construction — capability containment is the backstop
    guardrail against prompt injection from repository content.
    """

    def __init__(
        self,
        repository_id: str,
        chunk_searcher: ChunkSearcher,
        file_content_reader: FileContentReader,
        embeddings: Embeddings,
        evidence_formatter: EvidenceFormatter,
        search_top_k: int,
    ) -> None:
        self._repository_id = repository_id
        self._chunk_searcher = chunk_searcher
        self._file_content_reader = file_content_reader
        self._embeddings = embeddings
        self._evidence_formatter = evidence_formatter
        self._search_top_k = search_top_k
        self._collected_evidence: list[Citation] = []

    @property
    def collected_evidence(self) -> list[Citation]:
        return list(self._collected_evidence)

    def build_tools(self) -> list[BaseTool]:
        # async def + @tool is unverified in langchain 1.x; StructuredTool.from_function
        # with coroutine= is the documented async path
        return [
            StructuredTool.from_function(
                coroutine=self._search_code,
                name="search_code",
                description=(
                    "Hybrid keyword+semantic search over the indexed code. Use for any "
                    "question about behavior or implementation. Optionally filter by "
                    "language (python, typescript, tsx, javascript, markdown, config, text) "
                    "or path_prefix (e.g. 'src/')."
                ),
            ),
            StructuredTool.from_function(
                coroutine=self._read_file_span,
                name="read_file_span",
                description=(
                    "Read lines start_line..end_line of one file. Use to expand context "
                    "around a promising search hit — a few dozen lines, not whole files."
                ),
            ),
            StructuredTool.from_function(
                coroutine=self._list_repository_structure,
                name="list_repository_structure",
                description=(
                    "Directory tree of indexed file paths, optionally under path_prefix. "
                    "Use first on broad 'how does this repo work' questions to orient."
                ),
            ),
            StructuredTool.from_function(
                coroutine=self._find_symbol,
                name="find_symbol",
                description=(
                    "Exact lookup of a function/class/method by name. Fastest route for "
                    "'where is X defined' questions."
                ),
            ),
        ]

    async def _search_code(
        self, query: str, language: str | None = None, path_prefix: str | None = None
    ) -> str:
        query_embedding = await self._embeddings.aembed_query(query)
        hits = await self._chunk_searcher.search(
            self._repository_id, query, query_embedding, self._search_top_k
        )
        # index-side filtering is repository-scoped only; argument filters apply here
        if language is not None:
            hits = [hit for hit in hits if hit.chunk.language == language]
        if path_prefix is not None:
            hits = [hit for hit in hits if hit.chunk.file_path.startswith(path_prefix)]
        if not hits:
            return EMPTY_RESULT_MESSAGE
        self._record_chunks([hit.chunk for hit in hits])
        return self._evidence_formatter.format_search_hits(hits)

    async def _read_file_span(self, file_path: str, start_line: int, end_line: int) -> str:
        file_span = await self._file_content_reader.read_span(
            self._repository_id, file_path, start_line, end_line
        )
        if file_span is None:
            # an error STRING, not an exception: the agent should see it and recover
            return MISSING_SPAN_MESSAGE
        self._collected_evidence.append(
            Citation(file_path=file_span.file_path, start_line=file_span.start_line,
                     end_line=file_span.end_line)
        )
        return self._evidence_formatter.format_file_span(file_span)

    async def _list_repository_structure(self, path_prefix: str | None = None) -> str:
        file_paths = await self._file_content_reader.list_paths(self._repository_id, path_prefix)
        if not file_paths:
            return EMPTY_RESULT_MESSAGE
        # structure is orientation, not citable evidence — deliberately not recorded
        return self._evidence_formatter.format_structure(file_paths)

    async def _find_symbol(self, symbol_name: str) -> str:
        chunks = await self._chunk_searcher.find_by_symbol(self._repository_id, symbol_name)
        if not chunks:
            return EMPTY_RESULT_MESSAGE
        self._record_chunks(chunks)
        return self._evidence_formatter.format_symbol_chunks(chunks)

    def _record_chunks(self, chunks: list[CodeChunk]) -> None:
        self._collected_evidence.extend(
            Citation(file_path=chunk.file_path, start_line=chunk.start_line,
                     end_line=chunk.end_line)
            for chunk in chunks
        )
