"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { getDashboard, type DashboardSummary } from "@/lib/api";
import { PageSkeleton, CardSkeleton } from "@/components/Skeleton";

const ScopeChart = dynamic(() => import("@/components/ScopeChart"), {
  ssr: false,
  loading: () => <CardSkeleton />,
});

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const dashboardQuery = useQuery<DashboardSummary>({
    queryKey: ["dashboard", user?.company_id],
    queryFn: getDashboard,
    enabled: !!user && !loading,
  });

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

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
    return <div className="p-8 text-[var(--danger)]">Error: {error}</div>;
  }

  if (!data) return null;

  const report = data.latest_report;

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-[var(--muted)]">
          {data.company.name} &middot; {data.company.industry}
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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

      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-[var(--muted)] text-sm">Confidence</p>
          <p className="text-xl font-bold">
            {report ? `${(report.confidence * 100).toFixed(0)}%` : "—"}
          </p>
        </div>
        <div className="card">
          <p className="text-[var(--muted)] text-sm">Reports</p>
          <p className="text-xl font-bold">{data.reports_count}</p>
        </div>
        <div className="card">
          <p className="text-[var(--muted)] text-sm">Data Uploads</p>
          <p className="text-xl font-bold">{data.data_uploads_count}</p>
        </div>
      </div>

      {/* Scope breakdown chart */}
      {report && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Emission Breakdown</h2>
          <ScopeChart
            data={[
              { name: "Scope 1", value: report.scope1, fill: "var(--scope1)" },
              { name: "Scope 2", value: report.scope2, fill: "var(--scope2)" },
              { name: "Scope 3", value: report.scope3, fill: "var(--scope3)" },
            ]}
          />
        </div>
      )}

      {/* Year-over-year trend */}
      {data.year_over_year && data.year_over_year.length > 1 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Year-over-Year Trend</h2>
          <YoyTable rows={data.year_over_year} />
        </div>
      )}

      {/* Quick actions */}
      <div className="flex gap-4">
        <button onClick={() => router.push("/upload")} className="btn-primary">
          Upload New Data
        </button>
        <button
          onClick={() => router.push("/reports")}
          className="btn-primary bg-transparent border border-[var(--primary)] text-[var(--primary)]"
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
    <div className="card">
      <p className="text-[var(--muted)] text-sm">{label}</p>
      <p className="text-xl font-bold" style={color ? { color } : undefined}>
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
