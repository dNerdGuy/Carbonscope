import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PageSkeleton } from "@/components/Skeleton";
import { ErrorCard } from "@/components/ErrorCard";
import {
  getRecommendations,
  type RecommendationSummary,
  type Recommendation,
} from "@/lib/api";

export const Route = createFileRoute("/recommendations/$reportId")({
  component: RecommendationsPage,
});

function RecommendationsPage() {
  const { user, loading } = useRequireAuth();
  const navigate = useNavigate();
  const { reportId } = Route.useParams();

  const { data, error, refetch } = useQuery<RecommendationSummary>({
    queryKey: ["recommendations", reportId],
    queryFn: () => getRecommendations(reportId),
    enabled: !!user && !!reportId,
  });

  if (loading || (!data && !error)) return <PageSkeleton />;
  if (error)
    return (
      <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
        <ErrorCard
          message={
            error instanceof Error
              ? error.message
              : "Failed to load recommendations"
          }
          onRetry={() => refetch()}
        />
      </div>
    );
  if (!data) return null;

  const { recommendations, summary } = data;

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight mb-2">
            Reduction Recommendations
          </h1>
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            {summary.recommendation_count} strategies &middot;{" "}
            {summary.quick_wins} quick wins
          </p>
        </div>
        <button
          onClick={() => history.back()}
          className="text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← Back
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            Potential Reduction
          </p>
          <p className="text-xl font-bold text-[var(--primary)]">
            {summary.total_reduction_tco2e.toLocaleString()} tCO₂e
          </p>
          <p className="text-xs text-[var(--muted)]">
            {summary.total_reduction_pct.toFixed(1)}% of total
          </p>
        </div>
        <div className="card">
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            Est. Annual Cost
          </p>
          <p className="text-xl font-bold">
            ${(summary.annual_cost_range_usd.min / 1000).toFixed(0)}k – $
            {(summary.annual_cost_range_usd.max / 1000).toFixed(0)}k
          </p>
        </div>
        <div className="card">
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            Quick Wins
          </p>
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
                <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
                  CO₂ Reduction
                </p>
                <p className="font-medium">
                  {rec.co2_reduction_tco2e.toLocaleString()} tCO₂e (
                  {rec.reduction_percentage.toFixed(1)}%)
                </p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
                  Annual Cost
                </p>
                <p className="font-medium">
                  ${(rec.annual_cost_usd.min / 1000).toFixed(0)}k – $
                  {(rec.annual_cost_usd.max / 1000).toFixed(0)}k
                </p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
                  Payback
                </p>
                <p className="font-medium">{rec.payback_years} years</p>
              </div>
              <div>
                <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
                  Co-benefits
                </p>
                <p className="font-medium">{rec.co_benefits.join(", ")}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
