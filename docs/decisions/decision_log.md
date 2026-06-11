# Decision log

| date | decision | why |
|---|---|---|
| 2026-06-11 | Agentic retrieval (LangGraph tool loop) over naive/single-shot RAG | code questions are heterogeneous: symbol lookups need keyword search, "how does X work" needs multi-hop reading; an agent picks per question; single-shot kept as comparison strategy |
| 2026-06-11 | OpenSearch as the only datastore | real BM25 + k-NN + metadata in one engine; one store keeps compose light; relational state would be Postgres in production |
| 2026-06-11 | k-NN engine: lucene (not faiss) | faiss silently re-normalizes stored vectors for cosine; lucene is the documented recommendation < 10M vectors; both support 3072 dims |
| 2026-06-11 | Hybrid fusion: native normalization-processor pipeline | weighted min-max score combination is a tuning knob rank-based RRF lacks; one round trip; eval harness tunes the weights |
| 2026-06-11 | Chat model gpt-5.4-mini | positioned by OpenAI for coding/sub-agent tool use; $0.75/$4.50 per MTok vs $2.50/$15 for gpt-5.4; escalation tier documented |
| 2026-06-11 | Embeddings text-embedding-3-large (3072 dims) | at demo scale the cost delta vs -small is cents, so buy the recall headroom; eval harness re-validates with --embedding-model |
| 2026-06-11 | LangChain core interfaces ARE the LLM ports | wrapping already-abstract provider-agnostic interfaces is single-implementation interface theater; provider swap = one line in the composition root |
| 2026-06-11 | Ingestion as in-process asyncio task | no queue infra for a demo; strong-ref task set + status doc; SQS + worker is the documented production path |
| 2026-06-11 | Chat history client-side | server stays stateless; persistence is listed future work |
| 2026-06-11 | StructuredTool.from_function(coroutine=…) over @tool on async def | @tool's async support is undocumented in langchain 1.x; the explicit form is verified |
| 2026-06-11 | SSE tests against finite streams only | httpx ASGITransport buffers entire bodies; infinite generators would hang tests |
| 2026-06-11 | shiki lazy-loaded client-side, plain numbered fallback first | highlighting is progressive enhancement; keeps the main bundle lean |
| 2026-06-11 | Evals run manually, never in CI | non-deterministic + costs real OpenAI tokens; reports are committed artifacts |
| 2026-06-11 | Citation grounding = parse → validate vs evidence → one retry | hard guarantee that cited spans were actually retrieved this turn |
