import json
import re
from app.llm.base import LLMProvider
from app.models import EvaluationScore

JUDGE_PROMPT = """You are an answer quality evaluator. Given a question, retrieved context, and generated answer, score the answer on three dimensions (1-5 each):

1. **Relevance**: Does the answer address the question? (1=completely off-topic, 5=directly answers)
2. **Faithfulness**: Is the answer supported by the context? (1=hallucinated, 5=fully grounded)
3. **Completeness**: Does the answer cover all relevant aspects from the context? (1=major gaps, 5=comprehensive)

Respond ONLY with valid JSON in this exact format:
{"relevance": N, "faithfulness": N, "completeness": N}"""


REFORMULATE_PROMPT = """The following question did not retrieve good results. Reformulate it to be more specific and likely to match relevant document chunks. Return ONLY the reformulated question, nothing else.

Original question: {question}
Previous answer quality was poor because the retrieved context was insufficient."""


def evaluate_answer(question: str, context_chunks: list[dict], answer: str, llm: LLMProvider) -> EvaluationScore:
    context_summary = "\n".join(
        f"- [{c['filename']}, p{c.get('page', '?')}]: {c['content'][:200]}..."
        for c in context_chunks
    )
    messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user", "content": f"Question: {question}\n\nContext:\n{context_summary}\n\nAnswer: {answer}"},
    ]

    response = llm.chat(messages, temperature=0.0)

    try:
        match = re.search(r'\{[^}]+\}', response)
        if match:
            scores = json.loads(match.group())
        else:
            scores = json.loads(response)
    except (json.JSONDecodeError, AttributeError):
        scores = {"relevance": 3, "faithfulness": 3, "completeness": 3}

    r = max(1, min(5, scores.get("relevance", 3)))
    f = max(1, min(5, scores.get("faithfulness", 3)))
    c = max(1, min(5, scores.get("completeness", 3)))

    return EvaluationScore(
        relevance=r,
        faithfulness=f,
        completeness=c,
        average=round((r + f + c) / 3, 2),
    )


def reformulate_query(question: str, llm: LLMProvider) -> str:
    messages = [
        {"role": "user", "content": REFORMULATE_PROMPT.format(question=question)},
    ]
    return llm.chat(messages, temperature=0.3)
