import { useRef, useState, useEffect } from 'react';
import { uploadDocument, deleteDocument, clearAllDocuments } from '../api';
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
  const prevStatus = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const [showBurst, setShowBurst] = useState(false);
  const [burstKey, setBurstKey] = useState(0);
  const [removing, setRemoving] = useState([]);   // doc_ids mid exit-animation
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);

  function celebrate() {
    setBurstKey((k) => k + 1);   // remount → replays animation every time
    setShowBurst(true);
    clearTimeout(burstTimer.current);
    burstTimer.current = setTimeout(() => setShowBurst(false), 1300);
  }

  // Fire the success burst when a document finishes background processing
  // (transitions to 'ready'), not merely when the upload POST returns.
  useEffect(() => {
    const map = {};
    let justFinished = false;
    for (const d of documents) {
      map[d.doc_id] = d.status;
      if (prevStatus.current !== null) {
        const prev = prevStatus.current[d.doc_id];
        if (d.status === 'ready' && prev !== 'ready') justFinished = true;
      }
    }
    prevStatus.current = map;          // null on first run → no celebrate on mount
    if (justFinished) celebrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents]);

  async function handleFiles(files) {
    if (!files || !files.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of files) {
        await uploadDocument(file);
      }
      await onRefresh();   // document appears as "processing"; burst fires when ready
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleClearAll() {
    setClearing(true);
    setError(null);
    try {
      await clearAllDocuments();
      await onRefresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setClearing(false);
      setConfirmClear(false);
    }
  }

  async function handleDelete(docId, e) {
    e.stopPropagation();
    setRemoving((r) => [...r, docId]);            // trigger exit animation first
    setTimeout(async () => {
      try {
        await deleteDocument(docId);
        await onRefresh();
      } catch (err) {
        setError(err.message);
      } finally {
        setRemoving((r) => r.filter((id) => id !== docId));
      }
    }, 320);                                       // match card-exit duration
  }

  return (
    <aside className="slide-in-left w-80 shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col h-full">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-[var(--color-border)]">
        <div className="group flex items-center gap-2.5">
          <div className="gradient-pan hover-wiggle w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--color-accent)] via-[var(--color-accent2)] to-[var(--color-accent)] flex items-center justify-center text-white font-bold text-sm cursor-default transition-transform duration-300 group-hover:scale-110 shadow-lg shadow-[var(--color-accent)]/20">
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
          className={`relative overflow-visible cursor-pointer rounded-xl px-4 py-6 text-center transition-all duration-200
            ${dragOver
              ? 'marching-ants glow-pulse bg-[var(--color-accent)]/10 scale-[1.03] border-2 border-transparent'
              : 'border-2 border-dashed border-[var(--color-border)] hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-surface2)]/40'}`}
        >
          {showBurst && <UploadBurst key={burstKey} />}

          <div className={`transition-opacity duration-200 ${showBurst ? 'opacity-0' : 'opacity-100'}`}>
            <div className="relative w-[22px] h-[22px] mx-auto mb-2">
              {uploading && (
                <span className="spin-ring absolute inset-[-7px] rounded-full border-2 border-[var(--color-accent)]/20 border-t-[var(--color-accent)]" />
              )}
              <UploadIcon
                className={`text-[var(--color-accent)] ${uploading ? 'float-pulse' : dragOver ? 'breathe' : 'bob'}`}
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
        <div className="flex items-center justify-between mb-2 min-h-[20px]">
          <span className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
            Documents ({documents.length})
          </span>
          <div className="flex items-center gap-2.5">
            {selected.length > 0 && (
              <span className="text-[11px] text-[var(--color-accent)]">
                {selected.length} scoped
              </span>
            )}
            {documents.length > 0 && (
              confirmClear ? (
                <span className="pop-in-up flex items-center gap-1.5 text-[11px]">
                  <span className="text-[var(--color-muted)]">Clear all?</span>
                  <button
                    onClick={handleClearAll}
                    disabled={clearing}
                    className="text-[#f85149] font-medium hover:underline active:scale-95 transition-transform disabled:opacity-50"
                  >
                    {clearing ? 'Clearing…' : 'Yes'}
                  </button>
                  <button
                    onClick={() => setConfirmClear(false)}
                    disabled={clearing}
                    className="text-[var(--color-muted)] hover:text-[var(--color-ink)] active:scale-95 transition-transform"
                  >
                    No
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => setConfirmClear(true)}
                  className="flex items-center gap-1 text-[11px] text-[var(--color-muted)] hover:text-[#f85149] active:scale-95 transition-all"
                  title="Remove all documents and chunks"
                >
                  <TrashIcon width={11} height={11} />
                  Clear all
                </button>
              )
            )}
          </div>
        </div>

        {documents.length === 0 ? (
          <p className="text-[12px] text-[var(--color-muted)] text-center py-8">
            No documents yet.<br />Upload one to get started.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {documents.map((doc, idx) => {
              const isSel = selected.includes(doc.doc_id);
              const isProcessing = doc.status === 'processing';
              const isError = doc.status === 'error';
              const isRemoving = removing.includes(doc.doc_id);
              const selectable = !isProcessing && !isError;
              return (
                <li
                  key={doc.doc_id}
                  onClick={() => selectable && !isRemoving && onToggleSelect(doc.doc_id)}
                  style={{ animationDelay: `${Math.min(idx, 8) * 0.04}s` }}
                  className={`group rounded-lg border px-3 py-2.5 transition-all duration-200 will-change-transform
                    ${isRemoving ? 'card-exit' : 'slide-in-left'}
                    ${selectable ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/20' : 'cursor-default'}
                    ${isSel
                      ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10'
                      : isError
                        ? 'border-[#f85149]/40 bg-[#f85149]/5'
                        : 'border-[var(--color-border)] hover:bg-[var(--color-surface2)] hover:border-[var(--color-accent)]/40'}
                    ${isProcessing ? 'opacity-90' : ''}`}
                >
                  <div className="flex items-start gap-2.5">
                    <div className="mt-0.5 relative w-4 h-4 flex items-center justify-center">
                      {isProcessing ? (
                        <span className="spin-ring w-4 h-4 rounded-full border-2 border-[var(--color-accent)]/25 border-t-[var(--color-accent)]" />
                      ) : isError ? (
                        <span className="text-[#f85149] text-sm leading-none">!</span>
                      ) : isSel ? (
                        <div className="w-4 h-4 rounded bg-[var(--color-accent)] flex items-center justify-center">
                          <CheckIcon width={12} height={12} className="text-white" />
                        </div>
                      ) : (
                        <FileIcon width={16} height={16} style={{ color: fileTypeColor(doc.file_type) }} />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12.5px] font-medium truncate">{doc.filename}</p>
                      {isProcessing ? (
                        <p className="text-[11px] text-[var(--color-accent)] flex items-center gap-1">
                          Processing<span className="processing-dots" />
                        </p>
                      ) : isError ? (
                        <p className="text-[11px] text-[#f85149] truncate" title={doc.error || 'Failed'}>
                          Failed — {doc.error || 'ingestion error'}
                        </p>
                      ) : (
                        <p className="text-[11px] text-[var(--color-muted)]">
                          {doc.chunk_count} chunks · {doc.file_type}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={(e) => handleDelete(doc.doc_id, e)}
                      className="hover-wiggle opacity-0 group-hover:opacity-100 text-[var(--color-muted)] hover:text-[#f85149] hover:scale-125 transition-all shrink-0"
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
            className="pop-in-up mt-3 w-full text-[11px] text-[var(--color-muted)] hover:text-[var(--color-ink)] py-1.5 rounded-lg hover:bg-[var(--color-surface2)] transition-colors"
          >
            Clear scope (query all documents)
          </button>
        )}
      </div>

      {/* Health footer */}
      <div className="px-5 py-3 border-t border-[var(--color-border)] flex items-center gap-2 text-[11px] text-[var(--color-muted)]">
        <span
          className={`relative w-2 h-2 rounded-full ${
            health?.groq_connected
              ? 'bg-[var(--color-accent2)] text-[var(--color-accent2)] live-ping'
              : 'bg-[#f85149]'
          }`}
        />
        {health
          ? `Groq ${health.groq_connected ? 'connected' : 'offline'} · ${health.chunks_count} chunks indexed`
          : 'Connecting…'}
      </div>
    </aside>
  );
}
