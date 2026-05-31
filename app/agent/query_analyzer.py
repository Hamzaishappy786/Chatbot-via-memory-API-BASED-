import json
import re
from app.llm.base import LLMProvider

ROUTER_PROMPT = """Classify the user's question into one retrieval strategy. Choose the BEST match:

- "text_search": Question about textual content, facts, definitions, procedures
- "visual_search": Question about images, charts, graphs, diagrams, visual elements
- "metadata_filter": Question targeting a specific document by name
- "hybrid": General question that could benefit from both text and visual search (DEFAULT)

Respond ONLY with valid JSON: {"strategy": "..."}"""


def analyze_query(question: str, llm: LLMProvider) -> str:
    messages = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": question},
    ]

    response = llm.chat(messages, temperature=0.0)

    try:
        match = re.search(r'\{[^}]+\}', response)
        if match:
            result = json.loads(match.group())
        else:
            result = json.loads(response)
        strategy = result.get("strategy", "hybrid")
        if strategy not in ("text_search", "visual_search", "metadata_filter", "hybrid"):
            return "hybrid"
        return strategy
    except (json.JSONDecodeError, AttributeError):
        return "hybrid"
