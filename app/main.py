import hashlib
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.models import HealthResponse
from app.ingestion.router import router as ingestion_router
from app.retrieval.router import router as query_router
from app.portfolio.router import router as portfolio_router
from app import dependencies as deps
from app.ingestion.service import ingest_document

logger = logging.getLogger("uvicorn.error")

PORTFOLIO_DOCS_DIR = Path(__file__).parent.parent / "portfolio_docs"
SUPPORTED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff",
                  ".pptx", ".docx", ".xlsx", ".xlsm", ".txt", ".md", ".csv"}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def auto_ingest_portfolio():
    """
    Scan portfolio_docs/ and ingest any file not already in the DB.
    Populates deps.portfolio_doc_ids so the portfolio agent is scoped to these docs.
    """
    if not PORTFOLIO_DOCS_DIR.exists():
        PORTFOLIO_DOCS_DIR.mkdir(parents=True)
        logger.info("Created portfolio_docs/ — drop your CV and project docs here.")
        return

    files = [f for f in PORTFOLIO_DOCS_DIR.iterdir()
             if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]

    if not files:
        logger.warning("portfolio_docs/ is empty. Add your CV to enable the Portfolio Agent.")
        return

    for file_path in files:
        content_hash = _sha256_file(file_path)
        existing = deps.metadata_db.get_document_by_hash(content_hash)

        if existing:
            logger.info(f"Portfolio doc already indexed: {file_path.name} (doc_id={existing['doc_id']})")
            deps.portfolio_doc_ids.append(existing["doc_id"])
            continue

        logger.info(f"Ingesting portfolio doc: {file_path.name} ...")
        try:
            doc_id = uuid.uuid4().hex[:12]
            ext = file_path.suffix.lower()
            deps.metadata_db.add_document(
                doc_id, file_path.name, ext, str(file_path), content_hash, status="processing"
            )
            result = ingest_document(
                doc_id,
                str(file_path),
                file_path.name,
                deps.llm,
                deps.embedding_service,
                deps.vector_store,
                deps.metadata_db,
            )
            deps.portfolio_doc_ids.append(result["doc_id"])
            logger.info(
                f"  → {file_path.name}: {result['chunk_count']} chunks, "
                f"{result['visual_elements']} visual elements (doc_id={result['doc_id']})"
            )
        except Exception as e:
            logger.error(f"  → Failed to ingest {file_path.name}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Warm up embedding model
    deps.embedding_service.embed(["warmup"])
    # 2. Auto-ingest portfolio documents
    auto_ingest_portfolio()
    yield
    deps.metadata_db.close()


app = FastAPI(
    title="Multimodal RAG — Portfolio Agent",
    description=(
        "Ask anything about Abdul Hanan's skills, experience, and projects. "
        "Powered by a hybrid RAG pipeline with Groq LLM inference."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio_router)   # serves / (UI) and /portfolio/ask
app.include_router(ingestion_router)   # /documents/*
app.include_router(query_router)       # /query


@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="healthy",
        groq_connected=deps.llm.is_connected(),
        embedding_model_loaded=deps.embedding_service.is_loaded,
        documents_count=deps.metadata_db.count_documents(),
        chunks_count=deps.metadata_db.count_chunks(),
    )


# Serve the built React app at "/" in production. Mounted LAST so all API routes
# above take precedence. In local dev (no build) this is skipped and Vite serves
# the frontend with a proxy to this backend.
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    logger.info(f"Serving frontend from {FRONTEND_DIST}")
