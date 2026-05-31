import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from app.config import settings


class EmbeddingService:
    def __init__(self):
        self._model: SentenceTransformer | None = None
        self._reranker: CrossEncoder | None = None

    def _load_model(self):
        if self._model is None:
            self._model = SentenceTransformer(settings.embedding_model)

    def _load_reranker(self):
        if self._reranker is None:
            self._reranker = CrossEncoder(settings.reranker_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=settings.embed_batch_size,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]

    @property
    def max_seq_length(self) -> int:
        """The model's hard token limit. Tokens beyond this are silently truncated."""
        self._load_model()
        return self._model.max_seq_length

    def count_tokens(self, text: str) -> int:
        """Count content tokens (excluding special tokens) the way the model sees them."""
        self._load_model()
        return len(self._model.tokenizer.encode(text, add_special_tokens=False))

    def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
        self._load_reranker()
        pairs = [(query, doc) for doc in documents]
        scores = self._reranker.predict(pairs)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        if top_n:
            ranked = ranked[:top_n]
        return ranked

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
