"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  getQuestionnaire,
  updateQuestion,
  exportQuestionnairePdf,
  type QuestionnaireDetail,
  type QuestionOut,
} from "@/lib/api";

export default function QuestionnaireDetailPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [detail, setDetail] = useState<QuestionnaireDetail | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editAnswer, setEditAnswer] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const fetchDetail = useCallback(async () => {
    try {
      const d = await getQuestionnaire(id);
      setDetail(d);
    } catch {
      setError("Failed to load questionnaire");
    }
  }, [id]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user && id) fetchDetail();
  }, [user, loading, router, id, fetchDetail]);

  async function handleSave(question: QuestionOut) {
    setSaving(true);
    try {
      const updated = await updateQuestion(id, question.id, {
        human_answer: editAnswer,
        status: "reviewed",
      });
      setDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          questions: prev.questions.map((q) => (q.id === updated.id ? updated : q)),
        };
      });
      setEditingId(null);
    } catch {
      setError("Failed to save answer");
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove(question: QuestionOut) {
    try {
      const updated = await updateQuestion(id, question.id, { status: "approved" });
      setDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          questions: prev.questions.map((q) => (q.id === updated.id ? updated : q)),
        };
      });
    } catch {
      setError("Failed to approve");
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
      setError("Failed to export PDF");
    }
  }

  const statusColor = (s: string) => {
    const m: Record<string, string> = {
      draft: "text-yellow-400",
      reviewed: "text-blue-400",
      approved: "text-green-400",
    };
    return m[s] || "text-gray-400";
  };

  if (loading || !detail) {
    return <div className="p-8 text-center text-[var(--muted)]">Loading…</div>;
  }

  const approvedCount = detail.questions.filter((q) => q.status === "approved").length;
  const totalCount = detail.questions.length;

  return (
    <div className="max-w-4xl mx-auto p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => router.push("/questionnaires")}
            className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] mb-2 inline-block"
          >
            ← Back to questionnaires
          </button>
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
      <div className="w-full h-2 bg-gray-800 rounded mb-6">
        <div
          className="h-2 bg-[var(--primary)] rounded transition-all"
          style={{ width: `${totalCount ? (approvedCount / totalCount) * 100 : 0}%` }}
        />
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-red-900/20 border border-red-800 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Questions */}
      <div className="space-y-4">
        {detail.questions.map((q) => (
          <div
            key={q.id}
            className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-5"
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <span className="text-sm font-mono text-[var(--muted)] mr-2">Q{q.question_number}</span>
                <span className="font-medium">{q.question_text}</span>
              </div>
              <span className={`text-xs font-medium uppercase ${statusColor(q.status)}`}>
                {q.status}
              </span>
            </div>

            {q.category && (
              <span className="inline-block text-xs bg-gray-800 text-[var(--muted)] px-2 py-0.5 rounded mb-3">
                {q.category}
              </span>
            )}

            {/* AI Draft */}
            {q.ai_draft_answer && (
              <div className="mb-3">
                <p className="text-xs text-[var(--muted)] mb-1">AI Draft {q.confidence ? `(${Math.round(q.confidence * 100)}% confidence)` : ""}</p>
                <p className="text-sm text-[var(--foreground)] bg-gray-900/50 rounded p-3">
                  {q.ai_draft_answer}
                </p>
              </div>
            )}

            {/* Human answer */}
            {q.human_answer && editingId !== q.id && (
              <div className="mb-3">
                <p className="text-xs text-[var(--muted)] mb-1">Your Answer</p>
                <p className="text-sm bg-green-900/10 border border-green-900/30 rounded p-3">
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
                  className="w-full rounded border border-[var(--card-border)] bg-gray-900 p-3 text-sm focus:outline-none focus:border-[var(--primary)]"
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
                    className="px-3 py-1.5 rounded bg-green-800/50 text-green-300 text-sm font-medium hover:bg-green-800/70"
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
