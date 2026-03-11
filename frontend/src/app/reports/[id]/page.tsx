"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { getReport, type EmissionReport } from "@/lib/api";
import ScopeChart from "@/components/ScopeChart";

export default function ReportDetailPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const [report, setReport] = useState<EmissionReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user && id) {
      getReport(id)
        .then(setReport)
        .catch((e) => setError(e.message));
    }
  }, [user, loading, router, id]);

  if (loading || (!report && !error)) {
    return <div className="p-8 text-[var(--muted)]">Loading report...</div>;
  }

  if (error) {
    return <div className="p-8 text-[var(--danger)]">Error: {error}</div>;
  }

  if (!report) return null;

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Emission Report — {report.year}
          </h1>
          <p className="text-[var(--muted)] text-sm">
            Generated {new Date(report.created_at).toLocaleString()} &middot;{" "}
            {report.methodology_version}
          </p>
        </div>
        <button
          onClick={() => router.back()}
          className="text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← Back
        </button>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-[var(--muted)] text-sm">Total</p>
          <p className="text-xl font-bold">{fmt(report.total)} tCO₂e</p>
        </div>
        <div className="card">
          <p className="text-sm" style={{ color: "var(--scope1)" }}>
            Scope 1
          </p>
          <p className="text-xl font-bold">{fmt(report.scope1)}</p>
        </div>
        <div className="card">
          <p className="text-sm" style={{ color: "var(--scope2)" }}>
            Scope 2
          </p>
          <p className="text-xl font-bold">{fmt(report.scope2)}</p>
        </div>
        <div className="card">
          <p className="text-sm" style={{ color: "var(--scope3)" }}>
            Scope 3
          </p>
          <p className="text-xl font-bold">{fmt(report.scope3)}</p>
        </div>
      </div>

      {/* Chart */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Scope Breakdown</h2>
        <ScopeChart
          data={[
            { name: "Scope 1", value: report.scope1, fill: "var(--scope1)" },
            { name: "Scope 2", value: report.scope2, fill: "var(--scope2)" },
            { name: "Scope 3", value: report.scope3, fill: "var(--scope3)" },
          ]}
        />
      </div>

      {/* Confidence */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Confidence</h2>
        <div className="flex items-center gap-4">
          <div className="flex-1 bg-[var(--card-border)] rounded-full h-3">
            <div
              className="h-3 rounded-full bg-[var(--primary)]"
              style={{ width: `${report.confidence * 100}%` }}
            />
          </div>
          <span className="font-bold">
            {(report.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Link href={`/recommendations/${id}`} className="btn-primary text-sm">
          🌱 View Reduction Recommendations
        </Link>
      </div>

      {/* Detailed breakdown */}
      {report.breakdown && Object.keys(report.breakdown).length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Detailed Breakdown</h2>
          <div className="space-y-2">
            {Object.entries(report.breakdown).map(([key, val]) => (
              <div
                key={key}
                className="flex justify-between text-sm border-b border-[var(--card-border)]/50 py-1.5"
              >
                <span className="text-[var(--muted)]">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="font-medium">
                  {typeof val === "number"
                    ? `${val.toLocaleString()} tCO₂e`
                    : String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sources */}
      {report.sources && report.sources.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-3">Data Sources</h2>
          <ul className="list-disc list-inside text-sm text-[var(--muted)] space-y-1">
            {report.sources.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Assumptions */}
      {report.assumptions && report.assumptions.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-3">Assumptions</h2>
          <ul className="list-disc list-inside text-sm text-[var(--muted)] space-y-1">
            {report.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function fmt(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}
