import uuid

from app.config import settings
from app.models import QueryResponse, Citation, EvaluationScore
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingService
from app.storage.vector_store import VectorStore
from app.storage.metadata_db import MetadataDB
from app.retrieval.retriever import hybrid_retrieve, expand_context
from app.retrieval.reranker import rerank_results
from app.generation.generator import (
    generate_answer, generate_general_answer, stream_answer, stream_general_answer,
)
from app.generation.evaluator import evaluate_answer, reformulate_query
from app.agent.query_analyzer import analyze_query
from app.agent.session import session_store


def _citation_dicts(chunks):
    return [
        {
            "doc_id": c["doc_id"],
            "filename": c["filename"],
            "page": c.get("page"),
            "chunk_text": c["content"][:300],
            "relevance_score": round(c.get("rerank_score", c.get("rrf_score", 0.0)), 4),
        }
        for c in chunks
    ]


def run_agent_stream(
    question: str,
    doc_ids: list[str] | None,
    llm: LLMProvider,
    embeddings: EmbeddingService,
    vector_store: VectorStore,
    metadata_db: MetadataDB,
    session_id: str | None = None,
    mode: str = "auto",
):
    """Generator yielding SSE events: 'meta' → many 'token' → 'done'.

    Streams a single answer (no eval-retry loop) for responsive UX; a lightweight
    evaluation is computed after the stream finishes and sent in the 'done' event.
    """
    if not session_id:
        session_id = uuid.uuid4().hex[:16]
    history = session_store.get_history(session_id)

    def emit_general(strategy):
        yield {"type": "meta", "answer_source": "general", "citations": [],
               "strategy": strategy, "session_id": session_id}
        acc = []
        for tok in stream_general_answer(question, llm, history=history):
            acc.append(tok)
            yield {"type": "token", "text": tok}
        answer = "".join(acc)
        session_store.append(session_id, question, answer)
        metadata_db.log_query(question, answer, strategy, 0, 0, 0, 0)
        yield {"type": "done", "answer_source": "general"}

    # ── GENERAL MODE ──
    if mode == "general":
        yield from emit_general("general_chat")
        return

    strategy = analyze_query(question, llm)
    retrieved = hybrid_retrieve(question, embeddings, vector_store, metadata_db, doc_ids=doc_ids, llm=llm)
    reranked = rerank_results(question, retrieved, embeddings)
    best_score = max((c.get("rerank_score", -99.0) for c in reranked), default=-99.0)

    # ── AUTO MODE: fall back to general if docs irrelevant ──
    if mode == "auto" and (not reranked or best_score < settings.relevance_gate):
        yield from emit_general("auto_general")
        return

    # ── DOCUMENTS MODE with nothing relevant ──
    if not reranked:
        msg = "No relevant documents found. Upload a document or switch to General chat mode."
        yield {"type": "meta", "answer_source": "documents", "citations": [],
               "strategy": strategy, "session_id": session_id}
        yield {"type": "token", "text": msg}
        session_store.append(session_id, question, msg)
        yield {"type": "done", "answer_source": "documents"}
        return

    # ── GROUNDED: stream the answer over expanded context ──
    chunks = expand_context(reranked, metadata_db)
    yield {"type": "meta", "answer_source": "documents", "citations": _citation_dicts(chunks),
           "strategy": strategy, "session_id": session_id}

    acc = []
    for tok in stream_answer(question, chunks, llm, history=history):
        acc.append(tok)
        yield {"type": "token", "text": tok}
    answer = "".join(acc)

    evaluation = evaluate_answer(question, chunks, answer, llm)
    session_store.append(session_id, question, answer)
    metadata_db.log_query(
        question, answer, strategy,
        evaluation.relevance, evaluation.faithfulness, evaluation.completeness, 0,
    )
    yield {
        "type": "done",
        "answer_source": "documents",
        "confidence": round(evaluation.average / 5.0, 2),
        "evaluation": evaluation.model_dump(),
    }


def _general_response(question, llm, history, session_id, metadata_db, strategy="general_chat"):
    """Answer from the model's general knowledge — no document grounding."""
    answer = generate_general_answer(question, llm, history=history)
    session_store.append(session_id, question, answer)
    metadata_db.log_query(question, answer, strategy, 0, 0, 0, 0)
    return QueryResponse(
        answer=answer,
        citations=[],
        confidence=None,
        evaluation=None,
        retries=0,
        strategy=strategy,
        session_id=session_id,
        answer_source="general",
    )


def run_agent(
    question: str,
    doc_ids: list[str] | None,
    llm: LLMProvider,
    embeddings: EmbeddingService,
    vector_store: VectorStore,
    metadata_db: MetadataDB,
    session_id: str | None = None,
    mode: str = "auto",
) -> QueryResponse:
    if not session_id:
        session_id = uuid.uuid4().hex[:16]
    history = session_store.get_history(session_id)

    # ── GENERAL MODE: skip retrieval entirely ──
    if mode == "general":
        return _general_response(question, llm, history, session_id, metadata_db)

    strategy = analyze_query(question, llm)

    # Retrieve + rerank once to see if documents are relevant (HyDE-enhanced)
    retrieved = hybrid_retrieve(question, embeddings, vector_store, metadata_db, doc_ids=doc_ids, llm=llm)
    reranked = rerank_results(question, retrieved, embeddings)
    best_score = max((c.get("rerank_score", -99.0) for c in reranked), default=-99.0)

    # ── AUTO MODE: decide based on relevance ──
    if mode == "auto":
        if not reranked or best_score < settings.relevance_gate:
            # Documents irrelevant → answer from general knowledge
            return _general_response(question, llm, history, session_id, metadata_db, strategy="auto_general")
        return _run_grounded_loop(question, doc_ids, llm, embeddings, vector_store,
                                  metadata_db, history, session_id, reranked, strategy)

    # ── DOCUMENTS MODE: grounded only ──
    if not reranked:
        answer = "No relevant documents found. Upload a document or switch to General chat mode."
        session_store.append(session_id, question, answer)
        return QueryResponse(
            answer=answer, citations=[], confidence=0.0,
            evaluation=None, retries=0, strategy=strategy,
            session_id=session_id, answer_source="documents",
        )
    return _run_grounded_loop(question, doc_ids, llm, embeddings, vector_store,
                              metadata_db, history, session_id, reranked, strategy)


def _run_grounded_loop(question, doc_ids, llm, embeddings, vector_store,
                       metadata_db, history, session_id, reranked, strategy):
    """Generate + self-evaluate with retry/reformulation, grounded in documents."""
    current_question = question
    best_answer = ""
    best_eval = EvaluationScore(relevance=1, faithfulness=1, completeness=1, average=1.0)
    best_chunks = expand_context(reranked, metadata_db)   # attach neighbour context
    retries = 0

    for attempt in range(1 + settings.max_retries):
        answer = generate_answer(current_question, best_chunks, llm, history=history)
        evaluation = evaluate_answer(current_question, best_chunks, answer, llm)

        if evaluation.average >= best_eval.average:
            best_answer = answer
            best_eval = evaluation

        if evaluation.average >= settings.eval_threshold:
            break

        if attempt < settings.max_retries:
            current_question = reformulate_query(question, llm)
            retries += 1
            retrieved = hybrid_retrieve(current_question, embeddings, vector_store, metadata_db, doc_ids=doc_ids, llm=llm)
            new_reranked = rerank_results(current_question, retrieved, embeddings)
            if new_reranked:
                best_chunks = expand_context(new_reranked, metadata_db)

    citations = [
        Citation(
            doc_id=c["doc_id"],
            filename=c["filename"],
            page=c.get("page"),
            chunk_text=c["content"][:300],
            relevance_score=round(c.get("rerank_score", c.get("rrf_score", 0.0)), 4),
        )
        for c in best_chunks
    ]

    session_store.append(session_id, question, best_answer)
    metadata_db.log_query(
        question, best_answer, strategy,
        best_eval.relevance, best_eval.faithfulness, best_eval.completeness, retries,
    )

    return QueryResponse(
        answer=best_answer,
        citations=citations,
        confidence=round(best_eval.average / 5.0, 2),
        evaluation=best_eval,
        retries=retries,
        strategy=strategy,
        session_id=session_id,
        answer_source="documents",
    )
