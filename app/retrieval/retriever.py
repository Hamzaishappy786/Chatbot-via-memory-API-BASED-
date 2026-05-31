from rank_bm25 import BM25Okapi

from app.config import settings
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingService
from app.storage.vector_store import VectorStore
from app.storage.metadata_db import MetadataDB


HYDE_PROMPT = (
    "Write a short, factual passage (2-3 sentences) that directly answers the "
    "question below, as if quoting from a relevant document. Do not add caveats "
    "or say you are unsure — just write the most likely answer text.\n\nQuestion: {q}"
)


def generate_hyde(query: str, llm: LLMProvider) -> str:
    """HyDE: a hypothetical answer passage, used for embedding instead of the bare query."""
    try:
        passage = llm.chat(
            [{"role": "user", "content": HYDE_PROMPT.format(q=query)}],
            temperature=0.3,
        )
        # Pair the hypothetical answer with the original query for a robust embedding.
        return f"{query}\n{passage}".strip()
    except Exception:
        return query  # fall back to the raw query on any failure


def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def vector_search(
    query: str,
    embeddings: EmbeddingService,
    vector_store: VectorStore,
    top_k: int,
    doc_ids: list[str] | None = None,
) -> list[str]:
    query_emb = embeddings.embed_query(query)
    where = None
    if doc_ids:
        where = {"doc_id": {"$in": doc_ids}}
    results = vector_store.query(query_emb, n_results=top_k, where=where)
    if results and results.get("ids") and results["ids"][0]:
        return results["ids"][0]
    return []


def bm25_search(
    query: str,
    metadata_db: MetadataDB,
    top_k: int,
    doc_ids: list[str] | None = None,
) -> list[str]:
    all_chunks = metadata_db.get_all_chunk_texts()
    if not all_chunks:
        return []

    if doc_ids:
        filtered = []
        for cid, text in all_chunks:
            parts = cid.split("_")
            chunk_doc_id = parts[0] if parts else ""
            if chunk_doc_id in doc_ids:
                filtered.append((cid, text))
        all_chunks = filtered

    if not all_chunks:
        return []

    chunk_ids = [c[0] for c in all_chunks]
    corpus = [c[1].lower().split() for c in all_chunks]

    bm25 = BM25Okapi(corpus)
    query_tokens = query.lower().split()
    scores = bm25.get_scores(query_tokens)

    ranked = sorted(zip(chunk_ids, scores), key=lambda x: x[1], reverse=True)
    return [cid for cid, _ in ranked[:top_k]]


def hybrid_retrieve(
    query: str,
    embeddings: EmbeddingService,
    vector_store: VectorStore,
    metadata_db: MetadataDB,
    top_k: int | None = None,
    doc_ids: list[str] | None = None,
    llm: LLMProvider | None = None,
) -> list[dict]:
    top_k = top_k or settings.retrieval_top_k

    # HyDE: embed a hypothetical answer for the dense search; keep the original
    # query for BM25 (which relies on the real keywords).
    vector_query = query
    if settings.use_hyde and llm is not None:
        vector_query = generate_hyde(query, llm)

    vec_results = vector_search(vector_query, embeddings, vector_store, top_k, doc_ids)
    bm25_results = bm25_search(query, metadata_db, top_k, doc_ids)

    fused = reciprocal_rank_fusion([vec_results, bm25_results], k=settings.rrf_k)

    results = []
    for chunk_id, rrf_score in fused[:top_k]:
        chunk = metadata_db.get_chunk_by_id(chunk_id)
        if chunk:
            results.append({
                "chunk_id": chunk_id,
                "content": chunk["content"],
                "doc_id": chunk["doc_id"],
                "filename": chunk["filename"],
                "page": chunk.get("page_number"),
                "chunk_type": chunk["chunk_type"],
                "chunk_index": chunk.get("chunk_index"),
                "rrf_score": rrf_score,
            })

    return results


def expand_context(chunks: list[dict], metadata_db: MetadataDB, window: int | None = None) -> list[dict]:
    """Parent-document retrieval: attach neighbouring chunks (±window) as `context`.

    The precise `content` is preserved for citations and reranking; `context`
    (original chunk plus its neighbours, in reading order) is what the generator
    sees, so the LLM gets the surrounding text without losing pinpoint citations.
    """
    window = settings.context_window if window is None else window
    if window <= 0:
        return chunks

    doc_cache: dict[str, list[dict]] = {}
    for ch in chunks:
        doc_id = ch["doc_id"]
        if doc_id not in doc_cache:
            doc_cache[doc_id] = metadata_db.get_chunks_for_document(doc_id)
        siblings = doc_cache[doc_id]

        pos = next((i for i, s in enumerate(siblings) if s["chunk_id"] == ch["chunk_id"]), None)
        if pos is None:
            ch["context"] = ch["content"]
            continue

        lo = max(0, pos - window)
        hi = min(len(siblings), pos + window + 1)
        ch["context"] = "\n".join(s["content"] for s in siblings[lo:hi])

    return chunks
