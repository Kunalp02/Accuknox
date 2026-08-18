import { useCallback, useEffect, useState } from "react";
import { api, Document, KnowledgeBase } from "../api";
import { PageHeader } from "../components/ui/page-header";
import { Card, CardHeader } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Field } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { cn } from "../lib/cn";

function docStatusVariant(status: string): "success" | "warning" | "danger" | "default" {
  if (status === "indexed") return "success";
  if (status === "pending" || status === "processing") return "warning";
  if (status === "failed") return "danger";
  return "default";
}

export default function KnowledgePage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [name, setName] = useState("");
  const [selectedKb, setSelectedKb] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadMsg, setUploadMsg] = useState("");

  const load = () => api.listKbs().then(setKbs);

  const loadDocuments = useCallback(async () => {
    if (!selectedKb) {
      setDocuments([]);
      return;
    }
    const docs = await api.listKbDocuments(selectedKb);
    setDocuments(docs);
  }, [selectedKb]);

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    loadDocuments();
    if (!selectedKb) return;
    const interval = setInterval(loadDocuments, 3000);
    return () => clearInterval(interval);
  }, [selectedKb, loadDocuments]);

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
    setUploadMsg("Document uploaded — indexing in background");
    e.target.value = "";
    await loadDocuments();
    setTimeout(() => setUploadMsg(""), 4000);
  };

  return (
    <div>
      <PageHeader
        title="Knowledge bases"
        description="Embeddings use nomic-embed-text via your LLM gateway. Documents are indexed into Qdrant."
      />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Create" />
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Button type="button" onClick={create}>Create knowledge base</Button>

          <div className="mt-6 border-t border-border pt-5">
            <h4 className="mb-3 text-sm font-semibold text-gray-900">Existing</h4>
            <div className="space-y-1">
              {kbs.map((kb) => (
                <button
                  key={kb.id}
                  type="button"
                  onClick={() => setSelectedKb(kb.id)}
                  className={cn(
                    "w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                    selectedKb === kb.id ? "bg-primary-subtle text-primary" : "hover:bg-gray-50 text-gray-700"
                  )}
                >
                  {kb.name}{" "}
                  <span className="font-mono text-xs text-gray-400">({kb.embed_model})</span>
                </button>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Documents" />
          {selectedKb ? (
            <div className="space-y-4">
              <p className="text-sm text-gray-500">Upload text files to index into Qdrant</p>
              <input
                type="file"
                accept=".txt,.md,.csv"
                onChange={upload}
                className="text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-primary-subtle file:px-4 file:py-2 file:text-sm file:font-medium file:text-primary hover:file:bg-indigo-100"
              />
              {uploadMsg && <p className="text-sm text-emerald-600">{uploadMsg}</p>}

              <div className="border-t border-border pt-4 space-y-2">
                {documents.length === 0 && (
                  <p className="text-sm text-gray-500">No documents yet</p>
                )}
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
                  >
                    <span className="text-sm text-gray-900 truncate">{doc.filename}</span>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant={docStatusVariant(doc.status)}>{doc.status}</Badge>
                      <span className="font-mono text-xs text-gray-400">{doc.chunk_count} chunks</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Select a knowledge base first</p>
          )}
        </Card>
      </div>
    </div>
  );
}
