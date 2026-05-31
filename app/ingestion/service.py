import uuid
from pathlib import Path

from app.config import settings
from app.ingestion.parsers.base import ParsedContent
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.image import ImageParser
from app.ingestion.parsers.pptx import PPTXParser
from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.xlsx import XLSXParser
from app.ingestion.parsers.txt import TXTParser
from app.ingestion.chunker import chunk_text_by_tokens
from app.ingestion.visual import describe_image
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingService
from app.storage.vector_store import VectorStore
from app.storage.metadata_db import MetadataDB

PARSERS = {
    ext: parser_cls
    for parser_cls in [PDFParser, ImageParser, PPTXParser, DOCXParser, XLSXParser, TXTParser]
    for ext in parser_cls.supported_extensions()
}


def get_parser(file_path: str):
    ext = Path(file_path).suffix.lower()
    parser_cls = PARSERS.get(ext)
    if not parser_cls:
        raise ValueError(f"Unsupported file type: {ext}")
    return parser_cls()


def ingest_document(
    file_path: str,
    filename: str,
    llm: LLMProvider,
    embeddings: EmbeddingService,
    vector_store: VectorStore,
    metadata_db: MetadataDB,
    content_hash: str | None = None,
) -> dict:
    doc_id = uuid.uuid4().hex[:12]
    ext = Path(filename).suffix.lower()

    metadata_db.add_document(doc_id, filename, ext, file_path, content_hash)

    parser = get_parser(file_path)
    content: ParsedContent = parser.parse(file_path)

    chunk_ids = []
    chunk_texts = []
    chunk_metadatas = []
    chunk_index = 0

    for block in content.text_blocks:
        chunks = chunk_text_by_tokens(block["text"], embeddings.count_tokens)
        for chunk in chunks:
            cid = f"{doc_id}_text_{chunk_index}"
            chunk_ids.append(cid)
            chunk_texts.append(chunk)
            chunk_metadatas.append({
                "doc_id": doc_id,
                "filename": filename,
                "chunk_type": "text",
                "page": block.get("page", 1),
            })
            metadata_db.add_chunk(cid, doc_id, chunk, "text", block.get("page"), chunk_index)
            chunk_index += 1

    visual_count = 0
    for img_data in content.images:
        if img_data.get("source") == "page_render":
            continue

        description = describe_image(llm, img_data["image_base64"])
        if description.startswith("[Image could not"):
            continue

        cid = f"{doc_id}_visual_{chunk_index}"
        chunk_ids.append(cid)
        chunk_texts.append(description)
        chunk_metadatas.append({
            "doc_id": doc_id,
            "filename": filename,
            "chunk_type": "visual",
            "page": img_data.get("page", 1),
        })
        metadata_db.add_chunk(cid, doc_id, description, "visual", img_data.get("page"), chunk_index)
        chunk_index += 1
        visual_count += 1

    if chunk_texts:
        embeddings_list = embeddings.embed(chunk_texts)
        vector_store.add(chunk_ids, embeddings_list, chunk_texts, chunk_metadatas)

    metadata_db.update_document_counts(doc_id, len(chunk_ids), visual_count)

    return {
        "doc_id": doc_id,
        "filename": filename,
        "file_type": ext,
        "chunk_count": len(chunk_ids),
        "visual_elements": visual_count,
    }
