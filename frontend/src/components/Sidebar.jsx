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

// Precompute a radial spray of particles (angle → tx/ty offset)
const BURST = Array.from({ length: 14 }, (_, i) => {
  const angle = (i / 14) * Math.PI * 2 + (i % 2 ? 0.22 : 0);
  const dist = 40 + (i % 3) * 14;
  const colors = ['#58a6ff', '#3fb950', '#d29922', '#e6edf3', '#bc8cff'];
  return {
    tx: Math.cos(angle) * dist,
    ty: Math.sin(angle) * dist,
    color: colors[i % colors.length],
    size: 4 + (i % 3) * 2,
    delay: (i % 5) * 0.015,
  };
});

function UploadBurst() {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
      {/* glow flash */}
      <div
        className="glow-flash absolute w-20 h-20 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(88,166,255,.7), transparent 70%)' }}
      />
      {/* ripple rings */}
      <div className="ripple-ring absolute w-12 h-12 rounded-full border-2 border-[var(--color-accent)]" />
      <div
        className="ripple-ring absolute w-12 h-12 rounded-full border border-[var(--color-accent2)]"
        style={{ animationDelay: '.13s' }}
      />
      {/* particle spray */}
      {BURST.map((p, i) => (
        <span
          key={i}
          className="particle absolute rounded-full"
          style={{
            '--tx': `${p.tx}px`,
            '--ty': `${p.ty}px`,
            width: p.size,
            height: p.size,
            background: p.color,
            boxShadow: `0 0 7px ${p.color}`,
            animationDelay: `${p.delay}s`,
          }}
        />
      ))}
      {/* success badge */}
      <div className="pop-spring relative w-12 h-12 rounded-full bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent2)] flex items-center justify-center shadow-lg shadow-[var(--color-accent)]/40">
        <CheckIcon className="check-pop text-white" width={26} height={26} />
      </div>
    </div>
  );
}

export default function Sidebar({ documents, selected, onToggleSelect, onRefresh, health }) {
  const fileInput = useRef(null);
  const burstTimer = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const [showBurst, setShowBurst] = useState(false);
  const [burstKey, setBurstKey] = useState(0);

  function celebrate() {
    setBurstKey((k) => k + 1);   // remount → replays animation every upload
    setShowBurst(true);
    clearTimeout(burstTimer.current);
    burstTimer.current = setTimeout(() => setShowBurst(false), 1300);
  }

  async function handleFiles(files) {
    if (!files || !files.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of files) {
        await uploadDocument(file);
      }
      await onRefresh();
      celebrate();
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
          className={`relative overflow-visible cursor-pointer rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors
            ${dragOver ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10' : 'border-[var(--color-border)] hover:border-[var(--color-accent)]/60'}`}
        >
          {showBurst && <UploadBurst key={burstKey} />}

          <div className={`transition-opacity duration-200 ${showBurst ? 'opacity-0' : 'opacity-100'}`}>
            <div className="relative w-[22px] h-[22px] mx-auto mb-2">
              {uploading && (
                <span className="spin-ring absolute inset-[-7px] rounded-full border-2 border-[var(--color-accent)]/20 border-t-[var(--color-accent)]" />
              )}
              <UploadIcon
                className={`text-[var(--color-accent)] ${uploading ? 'float-pulse' : ''}`}
                width={22} height={22}
              />
            </div>
            <p className="text-[13px] font-medium">
              {uploading ? 'Uploading…' : 'Drop files or click to upload'}
            </p>
            <p className="text-[11px] text-[var(--color-muted)] mt-1">
              PDF · DOCX · PPTX · XLSX · images · txt
            </p>
          </div>
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
