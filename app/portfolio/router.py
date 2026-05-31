from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app import dependencies as deps
from app.portfolio.agent import ask_portfolio

router = APIRouter(tags=["Portfolio"])

# Resolved at import time — points to static/index.html
_HTML_PATH = Path(__file__).parent.parent.parent / "static" / "index.html"


class PortfolioRequest(BaseModel):
    question: str
    session_id: str | None = None


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def portfolio_ui():
    """Serve the chat UI at the root."""
    return HTMLResponse(_HTML_PATH.read_text(encoding="utf-8"))


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
