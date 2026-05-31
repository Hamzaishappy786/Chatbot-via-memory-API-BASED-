from pathlib import Path
import chromadb
from app.config import settings


class VectorStore:
    def __init__(self):
        Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]):
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, query_embedding: list[float], n_results: int = 20, where: dict | None = None) -> dict:
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        return self._collection.query(**kwargs)

    def delete_by_doc_id(self, doc_id: str):
        self._collection.delete(where={"doc_id": doc_id})

    def clear(self):
        """Drop every vector by deleting and recreating the collection."""
        self._client.delete_collection(name=settings.chroma_collection)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self._collection.count()
