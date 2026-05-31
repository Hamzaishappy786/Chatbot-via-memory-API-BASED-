from datetime import datetime
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    chunk_count: int
    created_at: str


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    chunk_count: int
    visual_elements: int
    message: str


class QueryRequest(BaseModel):
    question: str
    doc_ids: list[str] = Field(default_factory=list)
    session_id: str | None = Field(default=None, description="Session ID for multi-turn conversation. Omit to start a new session.")
    mode: str = Field(default="auto", description="'auto' (use docs when relevant, else general knowledge), 'documents' (docs only), or 'general' (general knowledge only).")


class Citation(BaseModel):
    doc_id: str
    filename: str
    page: int | None = None
    chunk_text: str
    relevance_score: float


class EvaluationScore(BaseModel):
    relevance: int
    faithfulness: int
    completeness: int
    average: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float | None = None
    evaluation: EvaluationScore | None = None
    retries: int
    strategy: str
    session_id: str | None = None
    answer_source: str = "documents"  # "documents" (grounded + cited) or "general" (model knowledge)


class HealthResponse(BaseModel):
    status: str
    groq_connected: bool
    embedding_model_loaded: bool
    documents_count: int
    chunks_count: int
