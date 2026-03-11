"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { listReports, type EmissionReport } from "@/lib/api";

export default function ReportsPage() {
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
      listReports()
        .then(setReports)
        .catch((e) => setError(e.message))
        .finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  if (loading || fetching) {
    return <div className="p-8 text-[var(--muted)]">Loading reports...</div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Emission Reports</h1>
        <button
          onClick={() => router.push("/upload")}
          className="btn-primary text-sm"
        >
          + New Estimate
        </button>
      </div>

      {error && <div className="text-[var(--danger)] mb-4">{error}</div>}

      {reports.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-[var(--muted)] mb-4">
            No reports yet. Upload data to generate your first emission
            estimate.
          </p>
          <button
            onClick={() => router.push("/upload")}
            className="btn-primary"
          >
            Upload Data
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((r) => (
            <Link
              key={r.id}
              href={`/reports/${r.id}`}
              className="card block hover:border-[var(--primary)] transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg">{r.year}</span>
                  <span className="text-[var(--muted)] ml-3 text-sm">
                    {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="text-right">
                  <p className="font-bold">
                    {r.total.toLocaleString(undefined, {
                      maximumFractionDigits: 1,
                    })}{" "}
                    tCO₂e
                  </p>
                  <p className="text-sm text-[var(--muted)]">
                    {(r.confidence * 100).toFixed(0)}% confidence
                  </p>
                </div>
              </div>
              <div className="flex gap-6 mt-2 text-sm">
                <span style={{ color: "var(--scope1)" }}>
                  S1:{" "}
                  {r.scope1.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </span>
                <span style={{ color: "var(--scope2)" }}>
                  S2:{" "}
                  {r.scope2.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </span>
                <span style={{ color: "var(--scope3)" }}>
                  S3:{" "}
                  {r.scope3.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
