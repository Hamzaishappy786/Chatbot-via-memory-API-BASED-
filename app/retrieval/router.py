import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models import QueryRequest, QueryResponse
from app.agent.orchestrator import run_agent, run_agent_stream
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


@router.post("/query/stream")
def query_stream(request: QueryRequest):
    """Server-sent events: streams the answer token-by-token."""
    def event_source():
        try:
            for event in run_agent_stream(
                question=request.question,
                doc_ids=request.doc_ids or None,
                llm=deps.llm,
                embeddings=deps.embedding_service,
                vector_store=deps.vector_store,
                metadata_db=deps.metadata_db,
                session_id=request.session_id,
                mode=request.mode,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:  # surface errors to the client as a final event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
