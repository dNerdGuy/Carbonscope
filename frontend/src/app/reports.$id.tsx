import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import {
  getReport,
  exportReportPdf,
  getAuditTrail,
  type EmissionReport,
} from "@/lib/api";
import Breadcrumbs from "@/components/Breadcrumbs";
import { PageSkeleton, CardSkeleton } from "@/components/Skeleton";
import { ErrorCard } from "@/components/ErrorCard";
import { useToast } from "@/components/Toast";

const ScopeChart = lazy(() => import("@/components/ScopeChart"));
const ScopeChartLoading = () => <CardSkeleton />;

export const Route = createFileRoute("/reports/$id")({
  component: ReportDetailPage,
});

function ReportDetailPage() {
  useDocumentTitle("Report Details");
  const { user, loading } = useRequireAuth();
  const { id } = Route.useParams();
  const [exporting, setExporting] = useState(false);
  const { toast } = useToast();
  const [exportError, setExportError] = useState("");
  const [auditTrail, setAuditTrail] = useState<string | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);

  const reportQuery = useQuery<EmissionReport>({
    queryKey: ["report", id],
    queryFn: () => getReport(id),
    enabled: !!user && !loading && !!id,
  });

  const report = reportQuery.data ?? null;
  const error = reportQuery.error
    ? reportQuery.error instanceof Error
      ? reportQuery.error.message
      : "Failed to load report"
    : "";

  if (loading || reportQuery.isLoading) {
    return <PageSkeleton />;
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
        <ErrorCard message={error} onRetry={() => reportQuery.refetch()} />
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Reports", href: "/reports" },
          { label: `Report — ${report.year}` },
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight mb-2">
            Emission Report — {report.year}
          </h1>
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            Generated {new Date(report.created_at).toLocaleString()} &middot;{" "}
            {report.methodology_version}
          </p>
        </div>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
            Total
          </p>
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
        <Suspense fallback={<ScopeChartLoading />}>
          <ScopeChart
            data={[
              { name: "Scope 1", value: report.scope1, fill: "var(--scope1)" },
              { name: "Scope 2", value: report.scope2, fill: "var(--scope2)" },
              { name: "Scope 3", value: report.scope3, fill: "var(--scope3)" },
            ]}
          />
        </Suspense>
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
        <Link to={`/recommendations/${id}`} className="btn-primary text-sm">
          🌱 View Reduction Recommendations
        </Link>
        <button
          onClick={async () => {
            setExporting(true);
            try {
              const blob = await exportReportPdf(id);
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `report-${report.year}.pdf`;
              a.click();
              URL.revokeObjectURL(url);
              toast("PDF exported successfully", "success");
            } catch (e) {
              setExportError(
                e instanceof Error ? e.message : "PDF export failed",
              );
            } finally {
              setExporting(false);
            }
          }}
          disabled={exporting}
          className="btn-secondary text-sm"
        >
          {exporting ? "Exporting…" : "📄 Export PDF"}
        </button>
      </div>

      {exportError && (
        <div className="text-[var(--danger)] text-sm">{exportError}</div>
      )}

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

      {/* AI Audit Trail */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">AI Audit Trail</h2>
          {!auditTrail && (
            <button
              onClick={async () => {
                setAuditLoading(true);
                try {
                  const result = await getAuditTrail(id);
                  setAuditTrail(result.audit_trail);
                } catch (e) {
                  setExportError(
                    e instanceof Error
                      ? e.message
                      : "Failed to load audit trail",
                  );
                } finally {
                  setAuditLoading(false);
                }
              }}
              disabled={auditLoading}
              className="btn-secondary text-sm"
            >
              {auditLoading ? "Loading…" : "Generate Audit Trail"}
            </button>
          )}
        </div>
        {auditTrail ? (
          <pre className="bg-[var(--background)] border border-[var(--card-border)] rounded-lg p-4 text-sm whitespace-pre-wrap text-[var(--muted)] max-h-[400px] overflow-auto">
            {auditTrail}
          </pre>
        ) : (
          <p className="text-sm text-[var(--muted)]">
            Generate an AI-powered audit trail to understand how this
            report&apos;s estimates were derived.
          </p>
        )}
      </div>
    </div>
  );
}

function fmt(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}
