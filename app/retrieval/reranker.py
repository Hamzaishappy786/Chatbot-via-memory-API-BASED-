from app.config import settings
from app.llm.embeddings import EmbeddingService


def rerank_results(
    query: str,
    results: list[dict],
    embeddings: EmbeddingService,
    top_n: int | None = None,
) -> list[dict]:
    top_n = top_n or settings.rerank_top_n

    if not results:
        return []

    # Always run the cross-encoder so every returned chunk carries a rerank_score.
    # (Previously skipped when len(results) <= top_n, which left scores missing and
    #  broke relevance gating for small document sets.)
    documents = [r["content"] for r in results]
    ranked = embeddings.rerank(query, documents, top_n=top_n)

    reranked = []
    for orig_idx, score in ranked:
        entry = results[orig_idx].copy()
        entry["rerank_score"] = float(score)
        reranked.append(entry)

    return reranked
