from app.llm.base import LLMProvider

VISUAL_PROMPT = """Describe this image in detail for a document retrieval system. Include:
- Any text visible in the image
- Data from charts, graphs, or tables (include specific numbers)
- Diagrams and their relationships
- Key visual elements and their meaning

Be factual and specific. Do not speculate."""


def describe_image(llm: LLMProvider, image_base64: str) -> str:
    try:
        return llm.vision(VISUAL_PROMPT, image_base64)
    except Exception as e:
        return f"[Image could not be processed: {e}]"
