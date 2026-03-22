import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PageSkeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import { StatusMessage } from "@/components/StatusMessage";
import Breadcrumbs from "@/components/Breadcrumbs";
import {
  listReviews,
  createReview,
  reviewAction,
  listReports,
  type DataReview,
  type EmissionReport,
} from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  draft: "badge-muted",
  submitted: "badge-info",
  approved: "badge-success",
  rejected: "badge-danger",
  revision_requested: "badge-warning",
};

export const Route = createFileRoute("/reviews")({ component: ReviewsPage });

function ReviewsPage() {
  useDocumentTitle("Data Reviews");
  const { user, loading } = useRequireAuth();
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [selectedReport, setSelectedReport] = useState("");
  const [rejectTarget, setRejectTarget] = useState<string | null>(null);
  const [rejectNotes, setRejectNotes] = useState("");

  const reviewsQuery = useQuery<{ items: DataReview[] }>({
    queryKey: ["reviews", user?.company_id],
    queryFn: () => listReviews(),
    enabled: !!user && !loading,
  });

  const reportsQuery = useQuery<{ items: EmissionReport[] }>({
    queryKey: ["reviews-reports", user?.company_id],
    queryFn: () => listReports(),
    enabled: !!user && !loading,
  });

  const reviews = reviewsQuery.data?.items ?? [];
  const reports = reportsQuery.data?.items ?? [];

  useEffect(() => {
    if (reviewsQuery.error) {
      setError(
        reviewsQuery.error instanceof Error
          ? reviewsQuery.error.message
          : "Failed to load reviews",
      );
    }
  }, [reviewsQuery.error]);

  const handleCreate = async () => {
    if (!selectedReport) return;
    try {
      await createReview(selectedReport);
      await reviewsQuery.refetch();
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
      await reviewAction(reviewId, action, notes);
      await reviewsQuery.refetch();
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

  if (loading || reviewsQuery.isLoading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <div className="mx-auto max-w-5xl p-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Reviews" },
        ]}
      />
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Data Reviews</h1>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          New Review
        </button>
      </div>

      {error && <StatusMessage message={error} variant="error" />}

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
            <button onClick={handleCreate} className="btn-primary">
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
                  className={`rounded-full px-3 py-1 text-xs font-medium badge ${STATUS_STYLES[r.status] || "badge-muted"}`}
                >
                  {r.status}
                </span>
                {r.status === "draft" && (
                  <button
                    onClick={() => handleAction(r.id, "submit")}
                    className="btn-primary text-sm px-3 py-1"
                  >
                    Submit
                  </button>
                )}
                {r.status === "submitted" && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleAction(r.id, "approve")}
                      className="btn-primary text-sm px-3 py-1"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => setRejectTarget(r.id)}
                      className="btn-danger text-sm px-3 py-1"
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
          <div className="card p-12 text-center">
            <span className="text-4xl mb-3 block">📋</span>
            <p className="text-[var(--muted)] mb-2">No reviews yet</p>
            <p className="text-sm text-[var(--muted)]">
              Create one for an emission report to get started.
            </p>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!rejectTarget}
        title="Reject Review"
        message="Are you sure you want to reject this review? Please provide a reason below."
        confirmLabel="Reject"
        variant="danger"
        onConfirm={handleReject}
        onCancel={() => {
          setRejectTarget(null);
          setRejectNotes("");
        }}
      >
        <textarea
          className="input mt-3 w-full"
          rows={3}
          placeholder="Reason for rejection…"
          value={rejectNotes}
          onChange={(e) => setRejectNotes(e.target.value)}
          aria-label="Rejection reason"
        />
      </ConfirmDialog>
      {rejectTarget && (
        <div className="fixed inset-0 z-40" aria-hidden="true" />
      )}
    </div>
  );
}
