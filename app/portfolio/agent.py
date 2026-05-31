"""
Portfolio Agent — a recruiter-facing specialization of the RAG pipeline.

Differences from the generic agent:
- System prompt tuned for professional recruiter Q&A about Abdul Hanan
- Always scoped to portfolio_doc_ids (only Abdul Hanan's documents)
- Returns a simplified response shape (no raw evaluation internals)
"""
from app.config import settings
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingService
from app.storage.vector_store import VectorStore
from app.storage.metadata_db import MetadataDB
from app.retrieval.retriever import hybrid_retrieve, expand_context
from app.retrieval.reranker import rerank_results
from app.generation.evaluator import evaluate_answer, reformulate_query
from app.agent.query_analyzer import analyze_query
from app.agent.session import session_store
from app.models import EvaluationScore
import uuid

PORTFOLIO_SYSTEM_PROMPT = """You are a professional AI assistant representing Abdul Hanan, an AI/ML Engineer based in Pakistan.
Your role is to answer questions from recruiters, hiring managers, and potential collaborators clearly and confidently.

Guidelines:
1. Answer ONLY based on the context provided — do not invent experience or skills.
2. Refer to Abdul Hanan in the third person ("Abdul Hanan has...", "He built...", "His experience includes...").
3. Be specific — mention exact technologies, metrics, dates, and project names from the CV.
4. Highlight strengths naturally without being salesy.
5. For anything not covered in the documents (availability, rate, visa status), say:
   "That detail isn't in his portfolio — reach out directly at hananmanan144@gmail.com or linkedin.com/in/abdul-hanan-4bb30334a"
6. Keep answers concise. Recruiters are busy.
7. If the user asks a follow-up using pronouns ("he", "his", "that project"), resolve them from conversation history."""

PORTFOLIO_FALLBACK = (
    "I couldn't find specific information about that in Abdul Hanan's portfolio. "
    "For more details, reach out directly: hananmanan144@gmail.com "
    "or https://linkedin.com/in/abdul-hanan-4bb30334a"
)


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[{chunk['filename']}, Page {chunk.get('page', '?')}]"
        tag = "[Visual]" if chunk.get("chunk_type") == "visual" else "[Text]"
        parts.append(f"--- Chunk {i} {tag} {source} ---\n{chunk['content']}")
    return "\n\n".join(parts)


def _generate(question: str, chunks: list[dict], llm: LLMProvider, history: list[dict]) -> str:
    context = _build_context(chunks)
    messages = [{"role": "system", "content": PORTFOLIO_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {question}",
    })
    return llm.chat(messages, temperature=0.15)


def ask_portfolio(
    question: str,
    llm: LLMProvider,
    embeddings: EmbeddingService,
    vector_store: VectorStore,
    metadata_db: MetadataDB,
    portfolio_doc_ids: list[str] | None,
    session_id: str | None = None,
) -> dict:
    if not session_id:
        session_id = uuid.uuid4().hex[:16]

    history = session_store.get_history(session_id)
    strategy = analyze_query(question, llm)

    current_question = question
    best_answer = PORTFOLIO_FALLBACK
    best_eval = EvaluationScore(relevance=1, faithfulness=1, completeness=1, average=1.0)
    best_chunks: list[dict] = []
    retries = 0

    for attempt in range(1 + settings.max_retries):
        retrieved = hybrid_retrieve(
            current_question, embeddings, vector_store, metadata_db,
            doc_ids=portfolio_doc_ids or None, llm=llm,
        )
        reranked = expand_context(rerank_results(current_question, retrieved, embeddings), metadata_db)

        if not reranked:
            break

        answer = _generate(current_question, reranked, llm, history)
        evaluation = evaluate_answer(current_question, reranked, answer, llm)

        if evaluation.average >= best_eval.average:
            best_answer = answer
            best_eval = evaluation
            best_chunks = reranked

        if evaluation.average >= settings.eval_threshold:
            break

        if attempt < settings.max_retries:
            current_question = reformulate_query(question, llm)
            retries += 1

    session_store.append(session_id, question, best_answer)

    # Simplified citation format for the portfolio UI
    citations = [
        {
            "filename": c["filename"],
            "page": c.get("page"),
            "snippet": c["content"][:200],
        }
        for c in best_chunks[:3]  # top 3 only for clean UI
    ]

    return {
        "answer": best_answer,
        "citations": citations,
        "confidence": round(best_eval.average / 5.0, 2),
        "session_id": session_id,
        "retries": retries,
    }
