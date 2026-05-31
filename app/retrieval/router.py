from fastapi import APIRouter
from app.models import QueryRequest, QueryResponse
from app.agent.orchestrator import run_agent
from app import dependencies as deps

router = APIRouter(tags=["Query"])


@router.post("/query", response_model=QueryResponse)
def query_documents(request: QueryRequest):
    result = run_agent(
        question=request.question,
        doc_ids=request.doc_ids or None,
        llm=deps.llm,
        embeddings=deps.embedding_service,
        vector_store=deps.vector_store,
        metadata_db=deps.metadata_db,
        session_id=request.session_id,
        mode=request.mode,
    )
    return result
