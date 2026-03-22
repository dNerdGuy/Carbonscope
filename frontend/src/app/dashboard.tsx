import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { lazy, Suspense, useMemo } from "react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { getDashboard, type DashboardSummary } from "@/lib/api";
import { PageSkeleton, CardSkeleton } from "@/components/Skeleton";
import { ErrorCard } from "@/components/ErrorCard";
import { useEventSource } from "@/hooks/useEventSource";

const ScopeChart = lazy(() => import("@/components/ScopeChart"));
const ScopeChartLoading = () => <CardSkeleton />;

export const Route = createFileRoute("/dashboard")({
  component: DashboardPage,
});

function DashboardPage() {
  useDocumentTitle("Dashboard");
  const { user, loading } = useRequireAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Invalidate dashboard data when a new estimate completes in the background
  const sseHandlers = useMemo(
    () => ({
      estimate_completed: () =>
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    }),
    [queryClient],
  );
  useEventSource(sseHandlers, !!user);

  const dashboardQuery = useQuery<DashboardSummary>({
    queryKey: ["dashboard", user?.company_id],
    queryFn: () => getDashboard(),
    enabled: !!user && !loading,
  });

  const error =
    dashboardQuery.error instanceof Error ? dashboardQuery.error.message : "";

  const data = dashboardQuery.data ?? null;

  if (!loading && !user) {
    return null;
  }

  if (loading || (dashboardQuery.isLoading && !data && !error)) {
    return <PageSkeleton />;
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <ErrorCard
          message={error || "Failed to load dashboard"}
          onRetry={() => dashboardQuery.refetch()}
        />
      </div>
    );
  }

  if (!data) return null;

  const report = data.latest_report;

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8 animate-fade-up">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-extrabold tracking-tight">Dashboard</h1>
        <p className="text-[var(--muted)] text-base font-medium">
          {data.company.name} &middot; {data.company.industry}
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 animate-fade-up delay-100">
        <KpiCard
          label="Total Emissions"
          value={report ? `${fmt(report.total)} tCO₂e` : "—"}
        />
        <KpiCard
          label="Scope 1"
          value={report ? `${fmt(report.scope1)} tCO₂e` : "—"}
          color="var(--scope1)"
        />
        <KpiCard
          label="Scope 2"
          value={report ? `${fmt(report.scope2)} tCO₂e` : "—"}
          color="var(--scope2)"
        />
        <KpiCard
          label="Scope 3"
          value={report ? `${fmt(report.scope3)} tCO₂e` : "—"}
          color="var(--scope3)"
        />
      </div>

      {/* Empty state for new users without reports */}
      {!report && (
        <div className="card p-8 text-center space-y-3">
          <p className="text-4xl">📊</p>
          <h2 className="text-lg font-semibold">No emission reports yet</h2>
          <p className="text-[var(--muted)] text-sm max-w-md mx-auto">
            Upload your first emission data to see your carbon footprint
            breakdown, track trends, and generate compliance reports.
          </p>
          <button
            onClick={() => navigate({ to: "/upload" })}
            className="btn-primary mt-2"
          >
            Upload Your First Data
          </button>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-fade-up delay-200">
        <div className="card flex flex-col items-center text-center">
          <p className="text-[var(--muted)] text-sm font-medium tracking-wide uppercase">
            Confidence
          </p>
          <p className="text-3xl font-extrabold mt-2 text-transparent bg-clip-text bg-gradient-to-r from-[var(--primary)] to-[var(--info)]">
            {report ? `${(report.confidence * 100).toFixed(0)}%` : "—"}
          </p>
        </div>
        <div className="card flex flex-col items-center text-center">
          <p className="text-[var(--muted)] text-sm font-medium tracking-wide uppercase">
            Reports
          </p>
          <p className="text-3xl font-extrabold mt-2">{data.reports_count}</p>
        </div>
        <div className="card flex flex-col items-center text-center">
          <p className="text-[var(--muted)] text-sm font-medium tracking-wide uppercase">
            Data Uploads
          </p>
          <p className="text-3xl font-extrabold mt-2">
            {data.data_uploads_count}
          </p>
        </div>
      </div>

      {/* Scope breakdown chart */}
      {report && (
        <div className="card animate-fade-up delay-300">
          <h2 className="text-xl font-bold mb-6 tracking-tight">
            Emission Breakdown
          </h2>
          <Suspense fallback={<ScopeChartLoading />}>
            <ScopeChart
              data={[
                {
                  name: "Scope 1",
                  value: report.scope1,
                  fill: "var(--scope1)",
                },
                {
                  name: "Scope 2",
                  value: report.scope2,
                  fill: "var(--scope2)",
                },
                {
                  name: "Scope 3",
                  value: report.scope3,
                  fill: "var(--scope3)",
                },
              ]}
            />
          </Suspense>
        </div>
      )}

      {/* Year-over-year trend */}
      {data.year_over_year && data.year_over_year.length > 1 && (
        <div className="card animate-fade-up delay-400">
          <h2 className="text-xl font-bold mb-6 tracking-tight">
            Year-over-Year Trend
          </h2>
          <YoyTable rows={data.year_over_year} />
        </div>
      )}

      {/* Quick actions */}
      <div className="flex gap-4 animate-fade-up delay-500 pt-4">
        <button
          onClick={() => navigate({ to: "/upload" })}
          className="btn-primary shadow-lg shadow-[var(--primary)]/20"
        >
          Upload New Data
        </button>
        <button
          onClick={() => navigate({ to: "/reports" })}
          className="btn-secondary"
        >
          View Reports
        </button>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="card flex flex-col justify-center items-start gap-1 relative overflow-hidden group">
      {color && (
        <div
          className="absolute -top-10 -right-10 w-24 h-24 rounded-full opacity-10 blur-xl group-hover:scale-150 transition-transform duration-500"
          style={{ background: color }}
        />
      )}
      <p className="text-[var(--muted)] text-sm font-medium tracking-wide uppercase">
        {label}
      </p>
      <p
        className="text-3xl font-extrabold tracking-tight mt-1"
        style={color ? { color } : undefined}
      >
        {value}
      </p>
    </div>
  );
}

function YoyTable({
  rows,
}: {
  rows: {
    year: number;
    scope1: number;
    scope2: number;
    scope3: number;
    total: number;
  }[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[var(--muted)] text-left border-b border-[var(--card-border)]">
            <th className="py-2 pr-4">Year</th>
            <th className="py-2 pr-4">Scope 1</th>
            <th className="py-2 pr-4">Scope 2</th>
            <th className="py-2 pr-4">Scope 3</th>
            <th className="py-2">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.year}
              className="border-b border-[var(--card-border)]/50"
            >
              <td className="py-2 pr-4 font-medium">{r.year}</td>
              <td className="py-2 pr-4">{fmt(r.scope1)}</td>
              <td className="py-2 pr-4">{fmt(r.scope2)}</td>
              <td className="py-2 pr-4">{fmt(r.scope3)}</td>
              <td className="py-2 font-medium">{fmt(r.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function fmt(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}
