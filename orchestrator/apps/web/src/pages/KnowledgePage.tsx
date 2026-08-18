import { useEffect, useState } from "react";
import { api, KnowledgeBase } from "../api";

export default function KnowledgePage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [name, setName] = useState("");
  const [selectedKb, setSelectedKb] = useState<string | null>(null);

  const load = () => api.listKbs().then(setKbs);

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    await api.createKb(name);
    setName("");
    await load();
  };

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedKb) return;
    await api.uploadDoc(selectedKb, file);
    alert("Document uploaded — indexing in background");
    e.target.value = "";
  };

  return (
    <div className="stack">
      <h2 style={{ margin: 0 }}>Knowledge bases</h2>
      <p style={{ color: "var(--muted)", margin: 0 }}>
        Embeddings use <span className="mono">nomic-embed-text</span> via your LLM gateway
      </p>
      <div className="grid-2">
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Create</h3>
          <div className="field">
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <button type="button" onClick={create}>Create knowledge base</button>
          <hr style={{ border: "none", borderTop: "1px solid var(--border)" }} />
          <h4 style={{ margin: 0 }}>Existing</h4>
          {kbs.map((kb) => (
            <button
              key={kb.id}
              type="button"
              className="secondary"
              onClick={() => setSelectedKb(kb.id)}
              style={{ borderColor: selectedKb === kb.id ? "var(--accent)" : undefined }}
            >
              {kb.name} <span className="mono">({kb.embed_model})</span>
            </button>
          ))}
        </div>
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Upload document</h3>
          {selectedKb ? (
            <>
              <p style={{ color: "var(--muted)" }}>Upload text files to index into Qdrant</p>
              <input type="file" accept=".txt,.md,.csv" onChange={upload} />
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select a knowledge base first</p>
          )}
        </div>
      </div>
    </div>
  );
}
