from app.llm.groq_provider import GroqProvider
from app.llm.embeddings import EmbeddingService
from app.storage.vector_store import VectorStore
from app.storage.metadata_db import MetadataDB

llm = GroqProvider()
embedding_service = EmbeddingService()
vector_store = VectorStore()
metadata_db = MetadataDB()

# Populated at startup by auto_ingest_portfolio() in main.py
# Contains doc_ids for all files found in portfolio_docs/
portfolio_doc_ids: list[str] = []
