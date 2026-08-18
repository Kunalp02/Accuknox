import { useEffect, useState } from "react";
import { api, KnowledgeBase } from "../api";
import { PageHeader } from "../components/ui/page-header";
import { Card, CardHeader } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Field } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { cn } from "../lib/cn";

export default function KnowledgePage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [name, setName] = useState("");
  const [selectedKb, setSelectedKb] = useState<string | null>(null);
  const [uploadMsg, setUploadMsg] = useState("");

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
    setUploadMsg("Document uploaded — indexing in background");
    e.target.value = "";
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
          <CardHeader title="Upload document" />
          {selectedKb ? (
            <div className="space-y-3">
              <p className="text-sm text-gray-500">Upload text files to index into Qdrant</p>
              <input
                type="file"
                accept=".txt,.md,.csv"
                onChange={upload}
                className="text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-primary-subtle file:px-4 file:py-2 file:text-sm file:font-medium file:text-primary hover:file:bg-indigo-100"
              />
              {uploadMsg && <p className="text-sm text-emerald-600">{uploadMsg}</p>}
            </div>
          ) : (
            <p className="text-sm text-gray-500">Select a knowledge base first</p>
          )}
        </Card>
      </div>
    </div>
  );
}
