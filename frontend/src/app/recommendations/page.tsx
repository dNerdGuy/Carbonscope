"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { listReports, type EmissionReport } from "@/lib/api";
import Breadcrumbs from "@/components/Breadcrumbs";
import { PageSkeleton } from "@/components/Skeleton";

export default function RecommendationsIndexPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [reports, setReports] = useState<EmissionReport[]>([]);
  const [error, setError] = useState("");
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user) {
      setFetching(true);
      listReports({ limit: 50, sortBy: "created_at", order: "desc" })
        .then((res) => setReports(res.items))
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to load reports"))
        .finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  if (loading || fetching) {
    return <PageSkeleton />;
  }

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Recommendations" },
        ]}
      />

      <div>
        <h1 className="text-2xl font-bold">Reduction Recommendations</h1>
        <p className="text-[var(--muted)] text-sm">
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
          <p className="text-[var(--muted)] text-sm mb-4">
            Create an emission estimate first, then come back here for reduction
            recommendations.
          </p>
          <Link href="/upload" className="btn-primary inline-block">
            Upload Data
          </Link>
        </div>
      )}

      {reports.length > 0 && (
        <div className="grid gap-4">
          {reports.map((report) => (
            <Link
              key={report.id}
              href={`/recommendations/${report.id}`}
              className="card hover:ring-2 hover:ring-[var(--primary)] transition-all cursor-pointer"
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
