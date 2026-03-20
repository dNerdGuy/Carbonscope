"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import { PageSkeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  listReviews,
  createReview,
  reviewAction,
  listReports,
  type DataReview,
  type EmissionReport,
} from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-500/20 text-[var(--muted)]",
  submitted: "bg-blue-500/20 text-blue-400",
  approved: "bg-emerald-500/20 text-emerald-400",
  rejected: "bg-red-500/20 text-red-400",
  revision_requested: "bg-yellow-500/20 text-yellow-400",
};

export default function ReviewsPage() {
  useDocumentTitle("Data Reviews");
  const { user, loading } = useAuth();
  const router = useRouter();
  const [reviews, setReviews] = useState<DataReview[]>([]);
  const [reports, setReports] = useState<EmissionReport[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [selectedReport, setSelectedReport] = useState("");
  const [rejectTarget, setRejectTarget] = useState<string | null>(null);
  const [rejectNotes, setRejectNotes] = useState("");

  const fetchReviews = useCallback(async () => {
    try {
      const data = await listReviews();
      setReviews(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load reviews");
    }
  }, []);

  const fetchReports = useCallback(async () => {
    try {
      const data = await listReports();
      setReports(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load reports");
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    if (user) {
      fetchReviews();
      fetchReports();
    }
  }, [user, loading, router, fetchReviews, fetchReports]);

  const handleCreate = async () => {
    if (!selectedReport) return;
    try {
      const r = await createReview(selectedReport);
      setReviews((prev) => [r, ...prev]);
      setShowCreate(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create review");
    }
  };

  const handleAction = async (
    reviewId: string,
    action: string,
    notes?: string,
  ) => {
    try {
      const updated = await reviewAction(reviewId, action, notes);
      setReviews((prev) => prev.map((r) => (r.id === reviewId ? updated : r)));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  };

  const handleReject = async () => {
    if (!rejectTarget) return;
    await handleAction(rejectTarget, "reject", rejectNotes);
    setRejectTarget(null);
    setRejectNotes("");
  };

  if (loading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <main className="mx-auto max-w-5xl p-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Data Reviews</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-white hover:bg-emerald-700"
        >
          New Review
        </button>
      </div>

      {error && <p className="mb-4 text-red-400">{error}</p>}

      {showCreate && (
        <div className="mb-6 rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4">
          <h3 className="mb-2 font-semibold">Create Review for Report</h3>
          <div className="flex gap-4">
            <select
              className="input"
              value={selectedReport}
              onChange={(e) => setSelectedReport(e.target.value)}
              aria-label="Select report for review"
            >
              <option value="">Select a report...</option>
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.year} — {r.total.toFixed(1)} tCO₂e
                </option>
              ))}
            </select>
            <button
              onClick={handleCreate}
              className="rounded bg-emerald-600 px-4 py-2 text-white"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="text-[var(--muted)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {reviews.map((r) => (
          <div
            key={r.id}
            className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">
                  Report: {r.report_id.slice(0, 8)}...
                </p>
                <p className="text-sm text-[var(--muted)]">
                  Created: {new Date(r.created_at).toLocaleDateString()}
                  {r.reviewed_at &&
                    ` · Reviewed: ${new Date(r.reviewed_at).toLocaleDateString()}`}
                </p>
                {r.reviewer_notes && (
                  <p className="mt-1 text-sm text-[var(--foreground)]">
                    Notes: {r.reviewer_notes}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_STYLES[r.status] || "bg-gray-600"}`}
                >
                  {r.status}
                </span>
                {r.status === "draft" && (
                  <button
                    onClick={() => handleAction(r.id, "submit")}
                    className="rounded bg-blue-600 px-3 py-1 text-sm text-white"
                  >
                    Submit
                  </button>
                )}
                {r.status === "submitted" && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleAction(r.id, "approve")}
                      className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => setRejectTarget(r.id)}
                      className="rounded bg-red-600 px-3 py-1 text-sm text-white"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        {reviews.length === 0 && (
          <p className="text-[var(--muted)]">
            No reviews yet. Create one for an emission report.
          </p>
        )}
      </div>

      <ConfirmDialog
        open={!!rejectTarget}
        title="Reject Review"
        message="Are you sure you want to reject this review? Please provide a reason."
        confirmLabel="Reject"
        variant="danger"
        onConfirm={handleReject}
        onCancel={() => {
          setRejectTarget(null);
          setRejectNotes("");
        }}
      />
      {rejectTarget && (
        <div className="fixed inset-0 z-40" aria-hidden="true" />
      )}
    </main>
  );
}
