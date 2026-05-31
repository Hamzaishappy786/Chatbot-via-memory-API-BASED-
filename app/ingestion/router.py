import hashlib
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.models import UploadResponse, DocumentInfo
from app.ingestion.service import ingest_document
from app import dependencies as deps


def _sha256(file_obj) -> str:
    """Stream-hash a file object without loading it all into memory."""
    h = hashlib.sha256()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(65536), b""):
        h.update(chunk)
    file_obj.seek(0)
    return h.hexdigest()


def _run_ingestion(doc_id: str, file_path: str, filename: str):
    """Background worker: heavy parse/VLM/embed work, off the request thread."""
    try:
        ingest_document(
            doc_id,
            file_path,
            filename,
            deps.llm,
            deps.embedding_service,
            deps.vector_store,
            deps.metadata_db,
        )
    except Exception as e:
        # Mark the document failed but keep the row so the UI can show the error.
        deps.metadata_db.set_status(doc_id, "error", str(e)[:500])


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=UploadResponse)
def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    supported = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".pptx", ".docx", ".xlsx", ".xlsm", ".txt", ".md", ".csv"}
    if ext not in supported:
        raise HTTPException(400, f"Unsupported file type: {ext}. Supported: {', '.join(sorted(supported))}")

    # --- Dedup check: hash the file before touching the disk ---
    content_hash = _sha256(file.file)
    existing = deps.metadata_db.get_document_by_hash(content_hash)
    if existing:
        # A previously-failed record shouldn't block retrying the same file —
        # drop it and re-ingest below. Otherwise return the existing record.
        if existing.get("status") == "error":
            deps.vector_store.delete_by_doc_id(existing["doc_id"])
            deps.metadata_db.delete_document(existing["doc_id"])
        else:
            return UploadResponse(
                doc_id=existing["doc_id"],
                filename=existing["filename"],
                file_type=existing["file_type"],
                chunk_count=existing["chunk_count"],
                visual_elements=existing.get("visual_count", 0),
                message=f"Document already ingested (doc_id={existing['doc_id']}). Returning existing record.",
                status=existing.get("status", "ready"),
            )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Register the document immediately so it shows up in the UI right away,
    # then process it on a background thread. The request returns in ms.
    doc_id = uuid.uuid4().hex[:12]
    deps.metadata_db.add_document(doc_id, file.filename, ext, str(file_path), content_hash, status="processing")

    threading.Thread(
        target=_run_ingestion,
        args=(doc_id, str(file_path), file.filename),
        daemon=True,
    ).start()

    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        file_type=ext,
        chunk_count=0,
        visual_elements=0,
        message="Upload received — processing in the background.",
        status="processing",
    )


@router.get("/", response_model=list[DocumentInfo])
def list_documents():
    docs = deps.metadata_db.list_documents()
    return [
        DocumentInfo(
            doc_id=d["doc_id"],
            filename=d["filename"],
            file_type=d["file_type"],
            chunk_count=d["chunk_count"],
            created_at=str(d["created_at"]),
            status=d.get("status", "ready"),
            error=d.get("error"),
        )
        for d in docs
    ]


@router.get("/{doc_id}", response_model=DocumentInfo)
def get_document(doc_id: str):
    doc = deps.metadata_db.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return DocumentInfo(
        doc_id=doc["doc_id"],
        filename=doc["filename"],
        file_type=doc["file_type"],
        chunk_count=doc["chunk_count"],
        created_at=str(doc["created_at"]),
        status=doc.get("status", "ready"),
        error=doc.get("error"),
    )


@router.delete("/")
def clear_all_documents():
    """Wipe the entire workspace: all vectors, chunks, documents, and uploaded files."""
    docs = deps.metadata_db.list_documents()
    for d in docs:
        fp = d.get("file_path")
        if fp:
            Path(fp).unlink(missing_ok=True)

    deps.vector_store.clear()
    count = deps.metadata_db.clear_all()
    deps.portfolio_doc_ids.clear()
    return {"message": f"Cleared workspace — removed {count} document(s) and all chunks.", "deleted": count}


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    doc = deps.metadata_db.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    deps.vector_store.delete_by_doc_id(doc_id)
    deps.metadata_db.delete_document(doc_id)
    file_path = Path(doc["file_path"]) if doc.get("file_path") else None
    if file_path and file_path.exists():
        file_path.unlink()
    return {"message": f"Document {doc_id} deleted"}
