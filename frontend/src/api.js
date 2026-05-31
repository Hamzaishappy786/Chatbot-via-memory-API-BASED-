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
