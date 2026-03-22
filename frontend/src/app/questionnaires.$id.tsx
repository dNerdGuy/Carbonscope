import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import {
  getQuestionnaire,
  updateQuestion,
  exportQuestionnairePdf,
  type QuestionnaireDetail,
  type QuestionOut,
} from "@/lib/api";
import Breadcrumbs from "@/components/Breadcrumbs";
import { StatusMessage } from "@/components/StatusMessage";
import { ErrorCard } from "@/components/ErrorCard";
import { PageSkeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";

export const Route = createFileRoute("/questionnaires/$id")({
  component: QuestionnaireDetailPage,
});

function QuestionnaireDetailPage() {
  const { user, loading } = useRequireAuth();
  const { id } = Route.useParams();

  const {
    data: detail,
    error: fetchError,
    refetch,
  } = useQuery<QuestionnaireDetail>({
    queryKey: ["questionnaire", id],
    queryFn: () => getQuestionnaire(id),
    enabled: !!user && !!id,
  });

  useDocumentTitle(
    detail ? `Questionnaire — ${detail.questionnaire.title}` : "Questionnaire",
  );

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editAnswer, setEditAnswer] = useState("");
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  async function handleSave(question: QuestionOut) {
    setSaving(true);
    try {
      await updateQuestion(id, question.id, {
        human_answer: editAnswer,
        status: "reviewed",
      });
      await refetch();
      setEditingId(null);
      toast("Answer saved", "success");
    } catch {
      setActionError("Failed to save answer");
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove(question: QuestionOut) {
    try {
      await updateQuestion(id, question.id, {
        status: "approved",
      });
      await refetch();
      toast("Question approved", "success");
    } catch {
      setActionError("Failed to approve");
    }
  }

  async function handleExportPdf() {
    try {
      const blob = await exportQuestionnairePdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `questionnaire_${id.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setActionError("Failed to export PDF");
    }
  }

  const statusColor = (s: string) => {
    const m: Record<string, string> = {
      draft: "var(--warning)",
      reviewed: "var(--info)",
      approved: "var(--success)",
    };
    return m[s] || "var(--muted)";
  };

  if (loading || (!detail && !fetchError)) return <PageSkeleton />;
  if (fetchError)
    return (
      <div className="max-w-4xl mx-auto p-8">
        <ErrorCard
          message={
            fetchError instanceof Error
              ? fetchError.message
              : "Failed to load questionnaire"
          }
          onRetry={() => refetch()}
        />
      </div>
    );
  if (!detail) return null;

  const approvedCount = detail.questions.filter(
    (q) => q.status === "approved",
  ).length;
  const totalCount = detail.questions.length;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <Breadcrumbs
        items={[
          { label: "Questionnaires", href: "/questionnaires" },
          { label: detail.questionnaire.title },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{detail.questionnaire.title}</h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            {approvedCount}/{totalCount} questions approved
          </p>
        </div>
        <button
          onClick={handleExportPdf}
          className="px-4 py-2 rounded bg-[var(--primary)] text-black text-sm font-medium hover:opacity-90"
        >
          Export PDF
        </button>
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-[var(--card-border)] rounded mb-6">
        <div
          className="h-2 bg-[var(--primary)] rounded transition-all"
          style={{
            width: `${totalCount ? (approvedCount / totalCount) * 100 : 0}%`,
          }}
        />
      </div>

      {actionError && <StatusMessage message={actionError} variant="error" />}

      {/* Questions */}
      <div className="space-y-4">
        {detail.questions.map((q) => (
          <div
            key={q.id}
            className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-5"
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <span className="text-sm font-mono text-[var(--muted)] mr-2">
                  Q{q.question_number}
                </span>
                <span className="font-medium">{q.question_text}</span>
              </div>
              <span
                className="text-xs font-medium uppercase"
                style={{ color: statusColor(q.status) }}
              >
                {q.status}
              </span>
            </div>

            {q.category && (
              <span className="inline-block text-xs bg-[var(--card)] text-[var(--muted)] px-2 py-0.5 rounded mb-3">
                {q.category}
              </span>
            )}

            {/* AI Draft */}
            {q.ai_draft_answer && (
              <div className="mb-3">
                <p className="text-xs text-[var(--muted)] mb-1">
                  AI Draft{" "}
                  {q.confidence
                    ? `(${Math.round(q.confidence * 100)}% confidence)`
                    : ""}
                </p>
                <p className="text-sm text-[var(--foreground)] bg-[var(--background)]/50 rounded p-3">
                  {q.ai_draft_answer}
                </p>
              </div>
            )}

            {/* Human answer */}
            {q.human_answer && editingId !== q.id && (
              <div className="mb-3">
                <p className="text-xs text-[var(--muted)] mb-1">Your Answer</p>
                <p
                  className="text-sm rounded p-3"
                  style={{
                    background:
                      "color-mix(in srgb, var(--success) 10%, transparent)",
                    borderColor:
                      "color-mix(in srgb, var(--success) 20%, transparent)",
                    border: "1px solid",
                  }}
                >
                  {q.human_answer}
                </p>
              </div>
            )}

            {/* Edit mode */}
            {editingId === q.id ? (
              <div className="mt-3">
                <textarea
                  value={editAnswer}
                  onChange={(e) => setEditAnswer(e.target.value)}
                  rows={4}
                  className="w-full rounded border border-[var(--card-border)] bg-[var(--background)] p-3 text-sm focus:outline-none focus:border-[var(--primary)]"
                  placeholder="Write your answer…"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => handleSave(q)}
                    disabled={saving}
                    className="px-3 py-1.5 rounded bg-[var(--primary)] text-black text-sm font-medium hover:opacity-90"
                  >
                    {saving ? "Saving…" : "Save"}
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="px-3 py-1.5 rounded border border-[var(--card-border)] text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => {
                    setEditingId(q.id);
                    setEditAnswer(q.human_answer || q.ai_draft_answer || "");
                  }}
                  className="px-3 py-1.5 rounded border border-[var(--card-border)] text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
                >
                  Edit Answer
                </button>
                {q.status !== "approved" && (
                  <button
                    onClick={() => handleApprove(q)}
                    className="px-3 py-1.5 rounded text-sm font-medium"
                    style={{
                      background:
                        "color-mix(in srgb, var(--success) 30%, transparent)",
                      color: "var(--success)",
                    }}
                  >
                    Approve
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
