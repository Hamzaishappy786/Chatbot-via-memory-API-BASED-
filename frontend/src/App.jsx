import { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatPanel from './components/ChatPanel';
import { listDocuments, health as fetchHealth } from './api';

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState([]);
  const [health, setHealth] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
      setSelected((sel) => sel.filter((id) => docs.some((d) => d.doc_id === id)));
    } catch (e) {
      console.error('Failed to load documents:', e);
    }
  }, []);

  useEffect(() => {
    refresh();
    fetchHealth().then(setHealth).catch(() => setHealth(null));
    const t = setInterval(() => fetchHealth().then(setHealth).catch(() => {}), 15000);
    return () => clearInterval(t);
  }, [refresh]);

  const toggleSelect = (docId) =>
    setSelected((sel) =>
      sel.includes(docId) ? sel.filter((id) => id !== docId) : [...sel, docId]
    );

  return (
    <div className="flex h-full">
      <Sidebar
        documents={documents}
        selected={selected}
        onToggleSelect={toggleSelect}
        onRefresh={refresh}
        health={health}
      />
      <ChatPanel selectedDocIds={selected} documents={documents} />
    </div>
  );
}
