"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  getRecommendations,
  type RecommendationSummary,
  type Recommendation,
} from "@/lib/api";

export default function RecommendationsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { reportId } = useParams() as { reportId: string };
  const [data, setData] = useState<RecommendationSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user && reportId) {
      getRecommendations(reportId)
        .then(setData)
        .catch((e) => setError(e.message));
    }
  }, [user, loading, router, reportId]);

  if (loading || (!data && !error))
    return (
      <div className="p-8 text-[var(--muted)]">Loading recommendations...</div>
    );
  if (error)
    return <div className="p-8 text-[var(--danger)]">Error: {error}</div>;
  if (!data) return null;

  const { recommendations, summary } = data;

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Reduction Recommendations</h1>
          <p className="text-[var(--muted)] text-sm">
            {summary.recommendation_count} strategies &middot;{" "}
            {summary.quick_wins} quick wins
          </p>
        </div>
        <button
          onClick={() => router.back()}
          className="text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← Back
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-[var(--muted)] text-sm">Potential Reduction</p>
          <p className="text-xl font-bold text-[var(--primary)]">
            {summary.total_reduction_tco2e.toLocaleString()} tCO₂e
          </p>
          <p className="text-xs text-[var(--muted)]">
            {summary.total_reduction_pct.toFixed(1)}% of total
          </p>
        </div>
        <div className="card">
          <p className="text-[var(--muted)] text-sm">Est. Annual Cost</p>
          <p className="text-xl font-bold">
            ${(summary.annual_cost_range_usd.min / 1000).toFixed(0)}k – $
            {(summary.annual_cost_range_usd.max / 1000).toFixed(0)}k
          </p>
        </div>
        <div className="card">
          <p className="text-[var(--muted)] text-sm">Quick Wins</p>
          <p className="text-xl font-bold text-[var(--scope2)]">
            {summary.quick_wins}
          </p>
          <p className="text-xs text-[var(--muted)]">Easy / low-cost actions</p>
        </div>
      </div>

      {/* Recommendations list */}
      <div className="space-y-4">
        {recommendations.map((rec: Recommendation) => (
          <div key={rec.id} className="card space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-lg">{rec.title}</h3>
                <span
                  className="text-xs px-2 py-0.5 rounded"
                  style={{
                    background:
                      rec.scope === 1
                        ? "var(--scope1)"
                        : rec.scope === 2
                          ? "var(--scope2)"
                          : "var(--scope3)",
                    color: "#000",
                  }}
                >
                  Scope {rec.scope} – {rec.category}
                </span>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-[var(--primary)]">
                  Priority {(rec.priority_score * 100).toFixed(0)}
                </p>
                <p className="text-xs text-[var(--muted)]">
                  {rec.difficulty} &middot; {rec.cost_tier}
                </p>
              </div>
            </div>
            <p className="text-sm text-[var(--muted)]">{rec.description}</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <p className="text-[var(--muted)] text-xs">CO₂ Reduction</p>
                <p className="font-medium">
                  {rec.co2_reduction_tco2e.toLocaleString()} tCO₂e (
                  {rec.reduction_percentage.toFixed(1)}%)
                </p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-xs">Annual Cost</p>
                <p className="font-medium">
                  ${(rec.annual_cost_usd.min / 1000).toFixed(0)}k – $
                  {(rec.annual_cost_usd.max / 1000).toFixed(0)}k
                </p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-xs">Payback</p>
                <p className="font-medium">{rec.payback_years} years</p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-xs">Co-benefits</p>
                <p className="font-medium">{rec.co_benefits.join(", ")}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
