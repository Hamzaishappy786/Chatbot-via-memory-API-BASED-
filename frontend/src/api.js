// Thin client over the FastAPI backend. Vite proxies these paths to :8000 in dev.

async function handle(res) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

export async function listDocuments() {
  return handle(await fetch('/documents/'));
}

export async function uploadDocument(file) {
  const form = new FormData();
  form.append('file', file);
  return handle(await fetch('/documents/upload', { method: 'POST', body: form }));
}

export async function deleteDocument(docId) {
  return handle(await fetch(`/documents/${docId}`, { method: 'DELETE' }));
}

export async function clearAllDocuments() {
  return handle(await fetch('/documents/', { method: 'DELETE' }));
}

export async function query({ question, docIds, sessionId, mode }) {
  return handle(await fetch('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      doc_ids: docIds || [],
      session_id: sessionId || null,
      mode: mode || 'auto',
    }),
  }));
}

export async function health() {
  return handle(await fetch('/health'));
}

// Streamed query over SSE. Calls callbacks as events arrive.
export async function queryStream(
  { question, docIds, sessionId, mode },
  { onMeta, onToken, onDone, onError } = {}
) {
  try {
    const res = await fetch('/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        doc_ids: docIds || [],
        session_id: sessionId || null,
        mode: mode || 'auto',
      }),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, sep).trim();
        buffer = buffer.slice(sep + 2);
        if (!raw.startsWith('data:')) continue;
        const evt = JSON.parse(raw.slice(5).trim());
        if (evt.type === 'meta') onMeta?.(evt);
        else if (evt.type === 'token') onToken?.(evt.text);
        else if (evt.type === 'done') onDone?.(evt);
        else if (evt.type === 'error') onError?.(new Error(evt.message));
      }
    }
  } catch (e) {
    onError?.(e);
  }
}
