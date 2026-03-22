import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PageSkeleton } from "@/components/Skeleton";
import { ErrorCard } from "@/components/ErrorCard";
import Breadcrumbs from "@/components/Breadcrumbs";
import {
  getIndustryBenchmarks,
  getPeerComparison,
  type IndustryBenchmark,
  type PeerComparison,
} from "@/lib/api";

export const Route = createFileRoute("/benchmarks")({
  component: BenchmarksPage,
});

function BenchmarksPage() {
  useDocumentTitle("Benchmarks");
  const { user, loading } = useRequireAuth();
  const [industry, setIndustry] = useState("technology");

  const benchmarksQuery = useQuery<[IndustryBenchmark, PeerComparison]>({
    queryKey: ["benchmarks", user?.company_id, industry],
    queryFn: () =>
      Promise.all([getIndustryBenchmarks(industry), getPeerComparison()]),
    enabled: !!user && !loading,
  });

  const [benchmarks, peers] = benchmarksQuery.data ?? [null, null];
  const error =
    benchmarksQuery.error instanceof Error
      ? benchmarksQuery.error.message
      : benchmarksQuery.error
        ? "Failed to load benchmarks"
        : "";

  if (loading || benchmarksQuery.isLoading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Benchmarks" },
        ]}
      />
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-extrabold tracking-tight mb-2">
          Industry Benchmarks
        </h1>
        <select
          className="input w-auto"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          aria-label="Select industry"
        >
          {[
            "technology",
            "manufacturing",
            "finance",
            "energy",
            "retail",
            "healthcare",
          ].map((ind) => (
            <option key={ind} value={ind}>
              {ind.charAt(0).toUpperCase() + ind.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <ErrorCard message={error} onRetry={() => benchmarksQuery.refetch()} />
      )}

      {!benchmarks && !error && (
        <div className="card p-12 text-center">
          <span className="text-4xl mb-3 block">📊</span>
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            No benchmark data available
          </p>
          <p className="text-sm text-[var(--muted)]">
            Select an industry above to view benchmarks.
          </p>
        </div>
      )}

      {/* Benchmark metrics */}
      {benchmarks && (
        <section className="mb-8">
          <h2 className="mb-4 text-xl font-semibold">
            {industry.charAt(0).toUpperCase() + industry.slice(1)} Benchmarks
          </h2>

          {/* KPI cards */}
          <div className="grid gap-4 sm:grid-cols-3 mb-6">
            {Object.entries(benchmarks)
              .filter(
                ([, val]) => typeof val === "number" || typeof val === "string",
              )
              .map(([key, val]) => (
                <div key={key} className="card">
                  <p className="text-sm text-[var(--muted)]">
                    {key.replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 text-2xl font-bold">
                    {typeof val === "number"
                      ? val.toLocaleString()
                      : String(val)}
                  </p>
                </div>
              ))}
          </div>

          {/* Scope intensity bar chart */}
          {(() => {
            const s1 = (benchmarks as unknown as Record<string, unknown>)
              .scope1_per_employee as number | undefined;
            const s2 = (benchmarks as unknown as Record<string, unknown>)
              .scope2_per_employee as number | undefined;
            const s3 = (benchmarks as unknown as Record<string, unknown>)
              .scope3_per_employee as number | undefined;
            if (s1 == null && s2 == null && s3 == null) return null;
            const chartData = [
              { scope: "Scope 1", industry: s1 ?? 0 },
              { scope: "Scope 2", industry: s2 ?? 0 },
              { scope: "Scope 3", industry: s3 ?? 0 },
            ];
            return (
              <div className="card mb-4">
                <p className="text-sm font-medium text-[var(--muted)] mb-4">
                  Intensity per Employee (tCO₂e) — Industry Median
                </p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={chartData}
                    margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="var(--card-border)"
                    />
                    <XAxis dataKey="scope" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} unit=" t" />
                    <Tooltip
                      formatter={(v: number) => [
                        `${v.toLocaleString()} tCO₂e`,
                        "Industry median",
                      ]}
                    />
                    <Legend />
                    <Bar
                      dataKey="industry"
                      name="Industry median"
                      fill="var(--primary, #22c55e)"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            );
          })()}
        </section>
      )}

      {/* Peer comparison */}
      {peers && (
        <section>
          <h2 className="mb-4 text-xl font-semibold">Peer Comparison</h2>
          <div className="overflow-x-auto rounded-lg border border-[var(--card-border)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--card)] text-[var(--muted)]">
                <tr>
                  {Object.entries(peers)
                    .filter(
                      ([, val]) =>
                        typeof val === "number" || typeof val === "string",
                    )
                    .map(([key]) => (
                      <th key={key} className="px-4 py-3">
                        {key.replace(/_/g, " ")}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--card-border)]">
                <tr>
                  {Object.entries(peers)
                    .filter(
                      ([, val]) =>
                        typeof val === "number" || typeof val === "string",
                    )
                    .map(([key, val]) => (
                      <td key={key} className="px-4 py-3">
                        {typeof val === "number"
                          ? val.toLocaleString()
                          : String(val)}
                      </td>
                    ))}
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
