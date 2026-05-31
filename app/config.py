from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_text_model: str = "llama-3.1-8b-instant"
    # Llama 3.2 vision models were decommissioned by Groq; Llama 4 Scout is the
    # current multimodal model (handles images natively).
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    embedding_model: str = "all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    chroma_persist_dir: str = str(Path(__file__).resolve().parent.parent / "data" / "chroma")
    chroma_collection: str = "documents"
    sqlite_path: str = str(Path(__file__).resolve().parent.parent / "data" / "metadata.db")
    upload_dir: str = str(Path(__file__).resolve().parent.parent / "data" / "uploads")

    # Token-aware chunking. all-MiniLM-L6-v2 truncates anything beyond 256 tokens,
    # so chunks are sized in TOKENS (not characters) with headroom under that limit.
    chunk_tokens: int = 200          # target tokens per chunk (safe headroom under 256)
    chunk_overlap_tokens: int = 40   # token overlap between consecutive chunks
    embed_batch_size: int = 64       # batch size when embedding many chunks

    # Legacy character-based fallback (used only if tokenizer unavailable)
    chunk_size: int = 500
    chunk_overlap: int = 100

    retrieval_top_k: int = 20
    rerank_top_n: int = 5
    rrf_k: int = 60

    eval_threshold: float = 3.0
    max_retries: int = 2

    # In "auto" mode, if the best reranked chunk scores below this cross-encoder
    # logit, the documents are deemed irrelevant and the bot answers from general
    # knowledge instead. Observed scores: relevant ≈ -2..-4, irrelevant ≈ -10.
    relevance_gate: float = -6.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
