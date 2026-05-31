import { useState, useRef, useEffect } from 'react';
import { queryStream } from '../api';
import { SendIcon, SparkIcon } from './icons';

const DOC_SUGGESTIONS = [
  'Summarize the key points across these documents',
  'What are the main topics covered?',
  'Extract any names, dates, and figures mentioned',
  'What is the most important takeaway?',
];
const GENERAL_SUGGESTIONS = [
  'Explain how retrieval-augmented generation works',
  'What is the difference between precision and recall?',
  'Give me 3 tips for writing clean Python',
  'Summarize the transformer architecture',
];

const MODES = [
  { id: 'auto', label: 'Auto', hint: 'Use documents when relevant, else general knowledge' },
  { id: 'documents', label: 'Documents', hint: 'Answer only from your uploaded documents' },
  { id: 'general', label: 'General', hint: 'Answer from general knowledge only' },
];

function confidenceStyle(c) {
  if (c >= 0.8) return { label: 'High', cls: 'bg-[var(--color-accent2)]/15 text-[var(--color-accent2)] border-[var(--color-accent2)]/30' };
  if (c >= 0.6) return { label: 'Medium', cls: 'bg-[#d29922]/15 text-[#d29922] border-[#d29922]/30' };
  return { label: 'Low', cls: 'bg-[#f85149]/15 text-[#f85149] border-[#f85149]/30' };
}

function renderMarkdown(text, streaming) {
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>');
  if (streaming) html += '<span class="stream-caret"></span>';
  return { __html: html };
}

function BotMessage({ msg }) {
  const isGeneral = msg.answer_source === 'general';
  const conf = confidenceStyle(msg.confidence ?? 0);
  const ev = msg.evaluation;

  return (
    <div className="pop-in-up flex gap-3 max-w-3xl">
      <div className="pop-in w-8 h-8 rounded-full bg-[var(--color-surface2)] border border-[var(--color-border)] flex items-center justify-center shrink-0 mt-0.5">
        <SparkIcon width={15} height={15} className="text-[var(--color-accent)]" />
      </div>
      <div className="min-w-0">
        <div className="rounded-2xl rounded-tl-sm bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-3">
          <div className="text-[14px] leading-relaxed" dangerouslySetInnerHTML={renderMarkdown(msg.answer, msg.streaming)} />

          {!isGeneral && msg.citations?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
              <p className="text-[10.5px] uppercase tracking-wider text-[var(--color-muted)] mb-1.5">Sources</p>
              <div className="space-y-1.5">
                {msg.citations.map((c, i) => (
                  <div
                    key={i}
                    style={{ animationDelay: `${0.1 + i * 0.07}s` }}
                    className="pop-in-up flex gap-2 items-baseline text-[11.5px] bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg px-2.5 py-1.5 hover:border-[var(--color-accent2)]/50 transition-colors"
                  >
                    <span className="text-[var(--color-accent2)] font-medium shrink-0">
                      {c.filename}{c.page ? ` · p.${c.page}` : ''}
                    </span>
                    <span className="text-[var(--color-muted)] truncate">{c.chunk_text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* meta row */}
        <div className="flex items-center gap-2 mt-1.5 px-1 flex-wrap">
          {isGeneral ? (
            <span className="pop-in text-[10.5px] px-2 py-0.5 rounded-full border bg-[#d29922]/15 text-[#d29922] border-[#d29922]/30">
              💡 General knowledge — not from your documents
            </span>
          ) : msg.streaming ? null : (
            <>
              <span className={`pop-in text-[10.5px] px-2 py-0.5 rounded-full border ${conf.cls}`}>
                {conf.label} confidence · {Math.round((msg.confidence ?? 0) * 100)}%
              </span>
              {msg.strategy && (
                <span className="text-[10.5px] text-[var(--color-muted)]">strategy: {msg.strategy}</span>
              )}
              {ev && (
                <span className="text-[10.5px] text-[var(--color-muted)]">
                  R{ev.relevance}·F{ev.faithfulness}·C{ev.completeness}
                </span>
              )}
              {msg.retries > 0 && (
                <span className="text-[10.5px] text-[#d29922]">↻ {msg.retries} retr{msg.retries > 1 ? 'ies' : 'y'}</span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function UserMessage({ text }) {
  return (
    <div className="pop-in-up flex gap-3 max-w-3xl ml-auto flex-row-reverse">
      <div className="pop-in w-8 h-8 rounded-full bg-[var(--color-accent)] flex items-center justify-center shrink-0 mt-0.5 text-white text-[13px] font-semibold">
        Y
      </div>
      <div className="rounded-2xl rounded-tr-sm bg-[var(--color-accent)]/15 border border-[var(--color-accent)]/30 px-4 py-3 text-[14px] leading-relaxed">
        {text}
      </div>
    </div>
  );
}

export default function ChatPanel({ selectedDocIds, documents }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [mode, setMode] = useState('auto');
  const scrollRef = useRef(null);
  const taRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);

  // Update the last message (the streaming bot bubble) in place.
  const patchLast = (patch) =>
    setMessages((m) => m.map((msg, i) =>
      i === m.length - 1 ? { ...msg, ...(typeof patch === 'function' ? patch(msg) : patch) } : msg
    ));

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput('');
    if (taRef.current) taRef.current.style.height = 'auto';
    // push the user message + an empty streaming bot bubble
    setMessages((m) => [
      ...m,
      { role: 'user', text: q },
      { role: 'bot', answer: '', citations: [], answer_source: 'documents', streaming: true },
    ]);
    setBusy(true);

    await queryStream(
      { question: q, docIds: selectedDocIds, sessionId, mode },
      {
        onMeta: (meta) => {
          setSessionId(meta.session_id);
          patchLast({
            answer_source: meta.answer_source,
            citations: meta.citations || [],
            strategy: meta.strategy,
          });
        },
        onToken: (t) => patchLast((msg) => ({ answer: msg.answer + t })),
        onDone: (d) => patchLast({
          streaming: false,
          confidence: d.confidence,
          evaluation: d.evaluation,
        }),
        onError: (e) => patchLast((msg) => ({
          answer: (msg.answer || '') + `\n\n⚠️ ${e.message}`,
          streaming: false,
          answer_source: 'general',
        })),
      }
    );
    setBusy(false);
  }

  // Input usable unless in strict Documents mode with nothing uploaded
  const inputDisabled = mode === 'documents' && documents.length === 0;
  const suggestions = documents.length > 0 && mode !== 'general' ? DOC_SUGGESTIONS : GENERAL_SUGGESTIONS;

  const scopeLabel =
    mode === 'general'
      ? 'general knowledge'
      : selectedDocIds.length === 0
        ? `all ${documents.length} document${documents.length === 1 ? '' : 's'}`
        : `${selectedDocIds.length} selected document${selectedDocIds.length === 1 ? '' : 's'}`;

  const activeIndex = MODES.findIndex((m) => m.id === mode);

  return (
    <main className="slide-in-right flex-1 flex flex-col h-full min-w-0">
      {/* top bar */}
      <div className="px-6 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface)]/50 backdrop-blur flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-[14px] font-semibold">Chat</h2>
          <p className="text-[11.5px] text-[var(--color-muted)] truncate">
            {mode === 'general' ? 'Answering from general knowledge' : `Querying ${scopeLabel}`}
          </p>
        </div>

        {/* mode segmented control */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="relative flex rounded-lg border border-[var(--color-border)] p-0.5 bg-[var(--color-bg)]">
            {/* sliding active indicator */}
            <span
              className="absolute left-0.5 top-0.5 bottom-0.5 rounded-md bg-[var(--color-accent)] shadow-lg shadow-[var(--color-accent)]/30 transition-transform duration-300 ease-[cubic-bezier(.2,.7,.3,1)]"
              style={{ width: 'calc((100% - 4px) / 3)', transform: `translateX(${activeIndex * 100}%)` }}
            />
            {MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                title={m.hint}
                className={`relative z-10 flex-1 min-w-[84px] px-5 py-1.5 text-[12px] font-medium whitespace-nowrap transition-colors active:scale-95
                  ${mode === m.id ? 'text-white' : 'text-[var(--color-muted)] hover:text-[var(--color-ink)]'}`}
              >
                {m.label}
              </button>
            ))}
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => { setMessages([]); setSessionId(null); }}
              className="pop-in-up text-[12px] text-[var(--color-muted)] hover:text-[var(--color-ink)] px-3 py-1.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface2)] hover:-translate-y-0.5 active:scale-95 transition-all"
            >
              New chat
            </button>
          )}
        </div>
      </div>

      {/* messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto">
            <div className="glow-pulse breathe gradient-pan w-14 h-14 rounded-2xl bg-gradient-to-br from-[var(--color-accent)] via-[var(--color-accent2)] to-[var(--color-accent)] flex items-center justify-center mb-4 shadow-xl shadow-[var(--color-accent)]/30">
              <SparkIcon width={26} height={26} className="text-white" />
            </div>
            <h3 className="pop-in-up text-lg font-semibold mb-1.5">
              {mode === 'general' ? 'Ask me anything' : 'Ask your documents anything'}
            </h3>
            <p className="pop-in-up text-[13px] text-[var(--color-muted)] mb-6" style={{ animationDelay: '.06s' }}>
              {mode === 'general'
                ? 'General-purpose AI assistant. Switch to Auto or Documents to query your files.'
                : documents.length === 0
                  ? 'Upload a document, or just start chatting — Auto mode answers general questions too.'
                  : 'Hybrid retrieval + reranking + self-evaluation, with citations on every grounded answer.'}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full">
              {suggestions.map((s, i) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  style={{ animationDelay: `${0.12 + i * 0.07}s` }}
                  className="pop-in-up text-[12.5px] text-left px-3.5 py-2.5 rounded-xl border border-[var(--color-border)] hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-surface2)] hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/20 active:scale-95 transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) =>
            m.role === 'user'
              ? <UserMessage key={i} text={m.text} />
              : <BotMessage key={i} msg={m} />
          )
        )}
      </div>

      {/* input */}
      <div className="px-6 py-4 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-end gap-3 max-w-3xl mx-auto">
          <textarea
            ref={taRef}
            rows={1}
            value={input}
            disabled={inputDisabled}
            placeholder={inputDisabled ? 'Upload a document, or switch to Auto/General mode…' : 'Ask a question…'}
            onChange={(e) => {
              setInput(e.target.value);
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
            }}
            className="flex-1 resize-none bg-[var(--color-bg)] border border-[var(--color-border)] focus:border-[var(--color-accent)] focus:shadow-lg focus:shadow-[var(--color-accent)]/15 outline-none rounded-xl px-4 py-3 text-[14px] leading-relaxed max-h-36 disabled:opacity-50 transition-all"
          />
          <button
            onClick={() => send()}
            disabled={busy || !input.trim() || inputDisabled}
            className="group shrink-0 bg-[var(--color-accent)] text-white rounded-xl px-4 py-3 font-medium disabled:opacity-40 disabled:hover:scale-100 hover:opacity-90 hover:scale-105 active:scale-95 transition-all flex items-center gap-2 shadow-lg shadow-[var(--color-accent)]/20"
          >
            <SendIcon
              width={16} height={16}
              className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
            />
          </button>
        </div>
        <p className="text-center text-[11px] text-[var(--color-muted)] mt-2">
          Enter to send · Shift+Enter for newline · Mode: <span className="text-[var(--color-ink)]">{MODES.find((m) => m.id === mode)?.label}</span>
        </p>
      </div>
    </main>
  );
}
