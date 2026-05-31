import { useRef, useState } from 'react';
import { uploadDocument, deleteDocument } from '../api';
import { UploadIcon, FileIcon, TrashIcon, CheckIcon } from './icons';

const fileTypeColor = (ext) => {
  const map = {
    '.pdf': '#f85149', '.docx': '#58a6ff', '.pptx': '#d29922',
    '.xlsx': '#3fb950', '.xlsm': '#3fb950', '.txt': '#8b949e',
    '.md': '#8b949e', '.csv': '#3fb950',
  };
  return map[ext] || '#8b949e';
};

export default function Sidebar({ documents, selected, onToggleSelect, onRefresh, health }) {
  const fileInput = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);

  async function handleFiles(files) {
    if (!files || !files.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of files) {
        await uploadDocument(file);
      }
      await onRefresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(docId, e) {
    e.stopPropagation();
    try {
      await deleteDocument(docId);
      await onRefresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <aside className="w-80 shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col h-full">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent2)] flex items-center justify-center text-white font-bold text-sm">
            R
          </div>
          <div>
            <h1 className="text-sm font-semibold leading-tight">RAG Workspace</h1>
            <p className="text-[11px] text-[var(--color-muted)]">Multimodal document intelligence</p>
          </div>
        </div>
      </div>

      {/* Upload zone */}
      <div className="p-4">
        <div
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
          className={`cursor-pointer rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors
            ${dragOver ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10' : 'border-[var(--color-border)] hover:border-[var(--color-accent)]/60'}`}
        >
          <UploadIcon className="mx-auto mb-2 text-[var(--color-accent)]" width={22} height={22} />
          <p className="text-[13px] font-medium">
            {uploading ? 'Uploading…' : 'Drop files or click to upload'}
          </p>
          <p className="text-[11px] text-[var(--color-muted)] mt-1">
            PDF · DOCX · PPTX · XLSX · images · txt
          </p>
        </div>
        <input
          ref={fileInput} type="file" multiple hidden
          onChange={(e) => handleFiles(e.target.files)}
          accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.pptx,.docx,.xlsx,.xlsm,.txt,.md,.csv"
        />
        {error && <p className="mt-2 text-[11px] text-[#f85149]">{error}</p>}
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
            Documents ({documents.length})
          </span>
          {selected.length > 0 && (
            <span className="text-[11px] text-[var(--color-accent)]">
              {selected.length} scoped
            </span>
          )}
        </div>

        {documents.length === 0 ? (
          <p className="text-[12px] text-[var(--color-muted)] text-center py-8">
            No documents yet.<br />Upload one to get started.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {documents.map((doc) => {
              const isSel = selected.includes(doc.doc_id);
              return (
                <li
                  key={doc.doc_id}
                  onClick={() => onToggleSelect(doc.doc_id)}
                  className={`group rounded-lg border px-3 py-2.5 cursor-pointer transition-colors
                    ${isSel
                      ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10'
                      : 'border-[var(--color-border)] hover:bg-[var(--color-surface2)]'}`}
                >
                  <div className="flex items-start gap-2.5">
                    <div className="mt-0.5 relative">
                      {isSel ? (
                        <div className="w-4 h-4 rounded bg-[var(--color-accent)] flex items-center justify-center">
                          <CheckIcon width={12} height={12} className="text-white" />
                        </div>
                      ) : (
                        <FileIcon width={16} height={16} style={{ color: fileTypeColor(doc.file_type) }} />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12.5px] font-medium truncate">{doc.filename}</p>
                      <p className="text-[11px] text-[var(--color-muted)]">
                        {doc.chunk_count} chunks · {doc.file_type}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDelete(doc.doc_id, e)}
                      className="opacity-0 group-hover:opacity-100 text-[var(--color-muted)] hover:text-[#f85149] transition"
                      title="Delete"
                    >
                      <TrashIcon width={14} height={14} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {selected.length > 0 && (
          <button
            onClick={() => selected.forEach(onToggleSelect)}
            className="mt-3 w-full text-[11px] text-[var(--color-muted)] hover:text-[var(--color-ink)] py-1"
          >
            Clear scope (query all documents)
          </button>
        )}
      </div>

      {/* Health footer */}
      <div className="px-5 py-3 border-t border-[var(--color-border)] flex items-center gap-2 text-[11px] text-[var(--color-muted)]">
        <span className={`w-2 h-2 rounded-full ${health?.groq_connected ? 'bg-[var(--color-accent2)]' : 'bg-[#f85149]'}`} />
        {health
          ? `Groq ${health.groq_connected ? 'connected' : 'offline'} · ${health.chunks_count} chunks indexed`
          : 'Connecting…'}
      </div>
    </aside>
  );
}
