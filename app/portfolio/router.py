from fastapi import APIRouter
from pydantic import BaseModel
from app import dependencies as deps
from app.portfolio.agent import ask_portfolio

router = APIRouter(tags=["Portfolio"])


class PortfolioRequest(BaseModel):
    question: str
    session_id: str | None = None


@router.post("/portfolio/ask")
def portfolio_ask(request: PortfolioRequest):
    """Ask a question about Abdul Hanan. Returns recruiter-friendly answer + citations."""
    return ask_portfolio(
        question=request.question,
        llm=deps.llm,
        embeddings=deps.embedding_service,
        vector_store=deps.vector_store,
        metadata_db=deps.metadata_db,
        portfolio_doc_ids=deps.portfolio_doc_ids,
        session_id=request.session_id,
    )
