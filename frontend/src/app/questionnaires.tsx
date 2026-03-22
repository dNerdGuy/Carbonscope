import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import ConfirmDialog from "@/components/ConfirmDialog";
import Breadcrumbs from "@/components/Breadcrumbs";
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
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import { useToast } from "@/components/Toast";

export const Route = createFileRoute("/questionnaires")({
  component: QuestionnairesPage,
});

function QuestionnairesPage() {
  useDocumentTitle("Questionnaires");
  const { user, loading } = useRequireAuth();
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"list" | "upload" | "templates">(
    "list",
  );
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const { toast } = useToast();

  const dataQuery = useQuery<
    [{ items: QuestionnaireOut[] }, TemplateSummary[]]
  >({
    queryKey: ["questionnaires", user?.company_id],
    queryFn: () => Promise.all([listQuestionnaires(), listTemplates()]),
    enabled: !!user && !loading,
  });

  const questionnaires = dataQuery.data?.[0]?.items ?? [];
  const templates = dataQuery.data?.[1] ?? [];

  useEffect(() => {
    if (dataQuery.error) {
      setError("Failed to load data");
    }
  }, [dataQuery.error]);

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
  const ALLOWED_EXTENSIONS = ["pdf", "docx", "xlsx", "csv"];

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side validation
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(
        `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ").toUpperCase()}`,
      );
      e.target.value = "";
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(
        `File too large. Maximum size: ${MAX_FILE_SIZE / (1024 * 1024)} MB`,
      );
      e.target.value = "";
      return;
    }

    setUploading(true);
    setError("");
    try {
      const q = await uploadQuestionnaire(file);
      await extractQuestions(q.id);
      await dataQuery.refetch();
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
      await dataQuery.refetch();
      setActiveTab("list");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to apply template");
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteQuestionnaire(id);
      await dataQuery.refetch();
      toast("Questionnaire deleted", "success");
    } catch {
      setError("Failed to delete questionnaire");
    } finally {
      setDeleteTarget(null);
    }
  }

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      uploaded: "badge-warning",
      extracting: "badge-info",
      extracted: "badge-success",
      reviewed: "badge-muted",
      exported: "badge-muted",
    };
    return (
      <span
        className={`px-2 py-0.5 rounded text-xs font-medium badge ${colors[status] || "badge-muted"}`}
      >
        {status}
      </span>
    );
  };

  if (loading || dataQuery.isLoading) return <PageSkeleton />;

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Questionnaires" },
        ]}
      />
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">
        Sustainability Questionnaires
      </h1>

      {error && <StatusMessage message={error} variant="error" />}

      {/* Tabs */}
      <div
        className="flex gap-1 mb-6 border-b border-[var(--card-border)]/50"
        role="tablist"
        aria-label="Questionnaire sections"
      >
        {(["list", "upload", "templates"] as const).map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            aria-controls={`tabpanel-${tab}`}
            id={`tab-${tab}`}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              activeTab === tab
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {tab === "list"
              ? "My Questionnaires"
              : tab === "upload"
                ? "Upload Document"
                : "Template Library"}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {activeTab === "upload" && (
        <div
          role="tabpanel"
          id="tabpanel-upload"
          aria-labelledby="tab-upload"
          className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-8 text-center"
        >
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            Upload a sustainability questionnaire (PDF, DOCX, XLSX, or CSV). Our
            AI will extract questions and generate draft responses using your
            company data.
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
        <div
          role="tabpanel"
          id="tabpanel-templates"
          aria-labelledby="tab-templates"
          className="grid gap-4 md:grid-cols-2"
        >
          {templates.map((tpl) => (
            <div
              key={tpl.id}
              className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-5"
            >
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold">{tpl.title}</h3>
                <span className="text-xs badge-info px-2 py-0.5 rounded">
                  {tpl.framework}
                </span>
              </div>
              <p className="text-sm text-[var(--muted)] mb-3">
                {tpl.description}
              </p>
              <div className="flex items-center justify-between">
                <span className="text-xs text-[var(--muted)]">
                  {tpl.question_count} questions
                </span>
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
        <div
          role="tabpanel"
          id="tabpanel-list"
          aria-labelledby="tab-list"
          className="space-y-3"
        >
          {questionnaires.length === 0 ? (
            <div className="text-center py-16 rounded-xl border border-[var(--card-border)] bg-[var(--card)]">
              <span className="text-4xl mb-3 block">📋</span>
              <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
                No questionnaires yet
              </p>
              <p className="text-sm text-[var(--muted)]">
                Upload a document or apply a template to get started.
              </p>
            </div>
          ) : (
            questionnaires.map((q) => (
              <div
                key={q.id}
                className="card flex items-center justify-between"
              >
                <div className="flex-1">
                  <button
                    onClick={() => navigate({ to: `/questionnaires/${q.id}` })}
                    className="font-medium hover:text-[var(--primary)] text-left"
                  >
                    {q.title}
                  </button>
                  <div className="flex items-center gap-3 mt-1">
                    {statusBadge(q.status)}
                    <span className="text-xs text-[var(--muted)]">
                      {q.file_type.toUpperCase()} ·{" "}
                      {(q.file_size / 1024).toFixed(0)} KB
                    </span>
                    <span className="text-xs text-[var(--muted)]">
                      {new Date(q.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setDeleteTarget(q.id)}
                  className="text-[var(--muted)] hover:text-[var(--danger)] text-sm ml-4"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Questionnaire"
        message="This questionnaire and all its questions will be permanently removed. Continue?"
        confirmLabel="Delete"
        variant="danger"
        onConfirm={() => deleteTarget && handleDelete(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
