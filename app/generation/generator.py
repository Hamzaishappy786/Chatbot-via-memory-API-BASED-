from app.llm.base import LLMProvider

SYSTEM_PROMPT = """You are a precise document analysis assistant. Answer the user's question using ONLY the provided context chunks.

Rules:
1. Base your answer strictly on the provided context. Do not use external knowledge.
2. Cite your sources using [Source: filename, Page: N] format after each claim.
3. If the context does not contain enough information, say so explicitly.
4. Be specific — include exact numbers, names, and dates from the context.
5. For visual descriptions, note that they come from image analysis of the document.
6. If the user refers to something from earlier in the conversation (e.g. "he", "that project", "the same document"), use the conversation history to resolve the reference."""


def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[{chunk['filename']}, Page {chunk.get('page', '?')}]"
        tag = "[Visual]" if chunk.get("chunk_type") == "visual" else "[Text]"
        parts.append(f"--- Chunk {i} {tag} {source} ---\n{chunk['content']}")
    return "\n\n".join(parts)


GENERAL_SYSTEM_PROMPT = """You are a helpful, knowledgeable AI assistant. Answer the user's question clearly, accurately, and concisely using your general knowledge.

Rules:
1. Be friendly and direct. Use markdown (**bold**, lists) where it improves clarity.
2. If you are uncertain or the question is ambiguous, say so rather than guessing.
3. Use the conversation history to resolve references like "it", "that", "he".
4. You do NOT have access to the user's uploaded documents for this answer — you are answering from general knowledge."""


def generate_general_answer(
    question: str,
    llm: LLMProvider,
    history: list[dict] | None = None,
) -> str:
    messages = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})
    return llm.chat(messages, temperature=0.4)


def generate_answer(
    question: str,
    chunks: list[dict],
    llm: LLMProvider,
    history: list[dict] | None = None,
) -> str:
    context = build_context(chunks)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject prior conversation turns so the model can resolve references
    if history:
        messages.extend(history)

    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {question}",
    })

    return llm.chat(messages, temperature=0.1)
