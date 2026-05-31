import hashlib
import shutil
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
        return UploadResponse(
            doc_id=existing["doc_id"],
            filename=existing["filename"],
            file_type=existing["file_type"],
            chunk_count=existing["chunk_count"],
            visual_elements=existing.get("visual_count", 0),
            message=f"Document already ingested (doc_id={existing['doc_id']}). Returning existing record.",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = ingest_document(
            str(file_path),
            file.filename,
            deps.llm,
            deps.embedding_service,
            deps.vector_store,
            deps.metadata_db,
            content_hash=content_hash,
        )
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Ingestion failed: {e}")

    return UploadResponse(
        doc_id=result["doc_id"],
        filename=result["filename"],
        file_type=result["file_type"],
        chunk_count=result["chunk_count"],
        visual_elements=result["visual_elements"],
        message=f"Document ingested: {result['chunk_count']} chunks, {result['visual_elements']} visual elements",
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
    )


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
