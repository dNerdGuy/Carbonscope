"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  listQuestionnaires,
  uploadQuestionnaire,
  listTemplates,
  applyTemplate,
  deleteQuestionnaire,
  extractQuestions,
  type QuestionnaireOut,
  type TemplateSummary,
} from "@/lib/api";

export default function QuestionnairesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [questionnaires, setQuestionnaires] = useState<QuestionnaireOut[]>([]);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"list" | "upload" | "templates">("list");

  const fetchData = useCallback(async () => {
    try {
      const [qRes, tRes] = await Promise.all([
        listQuestionnaires(),
        listTemplates(),
      ]);
      setQuestionnaires(qRes.items);
      setTemplates(tRes);
    } catch {
      setError("Failed to load data");
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user) fetchData();
  }, [user, loading, router, fetchData]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const q = await uploadQuestionnaire(file);
      await extractQuestions(q.id);
      await fetchData();
      setActiveTab("list");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleApplyTemplate(templateId: string) {
    setError("");
    try {
      await applyTemplate(templateId);
      await fetchData();
      setActiveTab("list");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to apply template");
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteQuestionnaire(id);
      setQuestionnaires((prev) => prev.filter((q) => q.id !== id));
    } catch {
      setError("Failed to delete questionnaire");
    }
  }

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      uploaded: "bg-yellow-900/30 text-yellow-400",
      extracting: "bg-blue-900/30 text-blue-400",
      extracted: "bg-green-900/30 text-green-400",
      reviewed: "bg-purple-900/30 text-purple-400",
      exported: "bg-gray-900/30 text-gray-400",
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || "bg-gray-800 text-gray-400"}`}>
        {status}
      </span>
    );
  };

  if (loading) return <div className="p-8 text-center text-[var(--muted)]">Loading…</div>;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Sustainability Questionnaires</h1>

      {error && (
        <div className="mb-4 p-3 rounded bg-red-900/20 border border-red-800 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-[var(--card-border)]">
        {(["list", "upload", "templates"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {tab === "list" ? "My Questionnaires" : tab === "upload" ? "Upload Document" : "Template Library"}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {activeTab === "upload" && (
        <div className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-8 text-center">
          <p className="text-[var(--muted)] mb-4">
            Upload a sustainability questionnaire (PDF, DOCX, XLSX, or CSV). Our AI will extract
            questions and generate draft responses using your company data.
          </p>
          <label className="inline-block cursor-pointer">
            <input
              type="file"
              accept=".pdf,.docx,.xlsx,.csv"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
            <span className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-[var(--primary)] text-black font-medium hover:opacity-90 transition-opacity">
              {uploading ? "Processing…" : "Choose File & Upload"}
            </span>
          </label>
          <p className="text-xs text-[var(--muted)] mt-2">Max 10 MB</p>
        </div>
      )}

      {/* Templates tab */}
      {activeTab === "templates" && (
        <div className="grid gap-4 md:grid-cols-2">
          {templates.map((tpl) => (
            <div
              key={tpl.id}
              className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-5"
            >
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold">{tpl.title}</h3>
                <span className="text-xs bg-blue-900/30 text-blue-400 px-2 py-0.5 rounded">
                  {tpl.framework}
                </span>
              </div>
              <p className="text-sm text-[var(--muted)] mb-3">{tpl.description}</p>
              <div className="flex items-center justify-between">
                <span className="text-xs text-[var(--muted)]">{tpl.question_count} questions</span>
                <button
                  onClick={() => handleApplyTemplate(tpl.id)}
                  className="px-3 py-1.5 rounded bg-[var(--primary)] text-black text-sm font-medium hover:opacity-90"
                >
                  Use Template
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* List tab */}
      {activeTab === "list" && (
        <div className="space-y-3">
          {questionnaires.length === 0 ? (
            <p className="text-center text-[var(--muted)] py-12">
              No questionnaires yet. Upload a document or apply a template to get started.
            </p>
          ) : (
            questionnaires.map((q) => (
              <div
                key={q.id}
                className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4 flex items-center justify-between"
              >
                <div className="flex-1">
                  <button
                    onClick={() => router.push(`/questionnaires/${q.id}`)}
                    className="font-medium hover:text-[var(--primary)] transition-colors text-left"
                  >
                    {q.title}
                  </button>
                  <div className="flex items-center gap-3 mt-1">
                    {statusBadge(q.status)}
                    <span className="text-xs text-[var(--muted)]">
                      {q.file_type.toUpperCase()} · {(q.file_size / 1024).toFixed(0)} KB
                    </span>
                    <span className="text-xs text-[var(--muted)]">
                      {new Date(q.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(q.id)}
                  className="text-[var(--muted)] hover:text-[var(--danger)] text-sm ml-4"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
