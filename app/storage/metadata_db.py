import sqlite3
from pathlib import Path
from app.config import settings
from app.storage.schemas import SCHEMA_SQL


class MetadataDB:
    def __init__(self):
        Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA_SQL)
        self._migrate()

    def _migrate(self):
        """Add columns to existing DBs that predate schema changes."""
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(documents)").fetchall()}
        if "content_hash" not in cols:
            self._conn.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")
            self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash) WHERE content_hash IS NOT NULL")
            self._conn.commit()
        if "status" not in cols:
            # Pre-existing rows were ingested synchronously, so they are already done.
            self._conn.execute("ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'ready'")
            self._conn.commit()
        if "error" not in cols:
            self._conn.execute("ALTER TABLE documents ADD COLUMN error TEXT")
            self._conn.commit()

    def get_document_by_hash(self, content_hash: str) -> dict | None:
        """Return an existing document if the same file content was already ingested."""
        row = self._conn.execute(
            "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return dict(row) if row else None

    def add_document(self, doc_id: str, filename: str, file_type: str, file_path: str, content_hash: str | None = None, status: str = "ready"):
        self._conn.execute(
            "INSERT INTO documents (doc_id, filename, file_type, file_path, content_hash, status) VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, filename, file_type, file_path, content_hash, status),
        )
        self._conn.commit()

    def set_status(self, doc_id: str, status: str, error: str | None = None):
        self._conn.execute(
            "UPDATE documents SET status = ?, error = ? WHERE doc_id = ?",
            (status, error, doc_id),
        )
        self._conn.commit()

    def update_document_counts(self, doc_id: str, chunk_count: int, visual_count: int):
        self._conn.execute(
            "UPDATE documents SET chunk_count = ?, visual_count = ? WHERE doc_id = ?",
            (chunk_count, visual_count, doc_id),
        )
        self._conn.commit()

    def get_document(self, doc_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def list_documents(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, doc_id: str):
        self._conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        self._conn.commit()

    def clear_all(self) -> int:
        """Remove every document and chunk. Returns how many documents were deleted."""
        n = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        self._conn.execute("DELETE FROM chunks")
        self._conn.execute("DELETE FROM documents")
        self._conn.commit()
        return n

    def add_chunk(self, chunk_id: str, doc_id: str, content: str, chunk_type: str, page_number: int | None, chunk_index: int):
        self._conn.execute(
            "INSERT INTO chunks (chunk_id, doc_id, content, chunk_type, page_number, chunk_index) VALUES (?, ?, ?, ?, ?, ?)",
            (chunk_id, doc_id, content, chunk_type, page_number, chunk_index),
        )
        self._conn.commit()

    def get_chunks_for_document(self, doc_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE doc_id = ? ORDER BY chunk_index", (doc_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_chunk_by_id(self, chunk_id: str) -> dict | None:
        row = self._conn.execute("SELECT c.*, d.filename FROM chunks c JOIN documents d ON c.doc_id = d.doc_id WHERE c.chunk_id = ?", (chunk_id,)).fetchone()
        return dict(row) if row else None

    def get_all_chunk_texts(self) -> list[tuple[str, str]]:
        rows = self._conn.execute("SELECT chunk_id, content FROM chunks").fetchall()
        return [(r["chunk_id"], r["content"]) for r in rows]

    def log_query(self, question: str, answer: str, strategy: str, relevance: int, faithfulness: int, completeness: int, retries: int):
        self._conn.execute(
            "INSERT INTO query_logs (question, answer, strategy, relevance, faithfulness, completeness, retries) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (question, answer, strategy, relevance, faithfulness, completeness, retries),
        )
        self._conn.commit()

    def count_documents(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def count_chunks(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def close(self):
        self._conn.close()
