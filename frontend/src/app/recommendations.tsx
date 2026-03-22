import { createFileRoute } from "@tanstack/react-router";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { listReports, type EmissionReport } from "@/lib/api";
import Breadcrumbs from "@/components/Breadcrumbs";
import { PageSkeleton } from "@/components/Skeleton";

export const Route = createFileRoute("/recommendations")({
  component: RecommendationsIndexPage,
});

function RecommendationsIndexPage() {
  useDocumentTitle("Recommendations");
  const { user, loading } = useRequireAuth();

  const reportsQuery = useQuery({
    queryKey: ["recommendations-reports", user?.company_id],
    queryFn: () =>
      listReports({ limit: 50, sortBy: "created_at", order: "desc" }),
    enabled: !!user && !loading,
  });

  const reports: EmissionReport[] = reportsQuery.data?.items ?? [];
  const error = reportsQuery.error
    ? reportsQuery.error instanceof Error
      ? reportsQuery.error.message
      : "Failed to load reports"
    : "";

  if (loading || reportsQuery.isLoading) {
    return <PageSkeleton />;
  }

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Recommendations" },
        ]}
      />

      <div>
        <h1 className="text-3xl font-extrabold tracking-tight mb-2">
          Reduction Recommendations
        </h1>
        <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
          Select a report to view AI-generated reduction strategies.
        </p>
      </div>

      {error && (
        <div className="text-[var(--danger)] text-sm">Error: {error}</div>
      )}

      {reports.length === 0 && !error && (
        <div className="card text-center p-8">
          <div className="text-4xl mb-4">📊</div>
          <h2 className="text-lg font-semibold mb-2">No reports yet</h2>
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            Create an emission estimate first, then come back here for reduction
            recommendations.
          </p>
          <Link to="/upload" className="btn-primary inline-block">
            Upload Data
          </Link>
        </div>
      )}

      {reports.length > 0 && (
        <div className="grid gap-4">
          {reports.map((report) => (
            <Link
              key={report.id}
              to={`/recommendations/${report.id}`}
              className="card cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold">
                    {report.year} Emission Report
                  </h3>
                  <p className="text-sm text-[var(--muted)]">
                    {report.total.toLocaleString()} tCO₂e total &middot;{" "}
                    {(report.confidence * 100).toFixed(0)}% confidence
                  </p>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <div className="text-right">
                    <span className="text-xs text-[var(--muted)]">
                      Scope 1 / 2 / 3
                    </span>
                    <p className="font-medium">
                      {report.scope1.toLocaleString()} /{" "}
                      {report.scope2.toLocaleString()} /{" "}
                      {report.scope3.toLocaleString()}
                    </p>
                  </div>
                  <span className="text-[var(--primary)]">→</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
