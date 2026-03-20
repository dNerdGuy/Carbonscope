"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import {
  listReports,
  generateComplianceReport,
  type EmissionReport,
} from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";

type Framework = "ghg_protocol" | "cdp" | "tcfd" | "sbti";

const FRAMEWORKS: { id: Framework; label: string; desc: string }[] = [
  {
    id: "ghg_protocol",
    label: "GHG Protocol",
    desc: "Corporate Standard inventory with Scope 1/2/3 breakdown",
  },
  {
    id: "cdp",
    label: "CDP Climate Change",
    desc: "Questionnaire modules C0–C7 for CDP disclosure",
  },
  {
    id: "tcfd",
    label: "TCFD",
    desc: "Task Force on Climate-related Financial Disclosures (4 pillars)",
  },
  {
    id: "sbti",
    label: "SBTi Pathway",
    desc: "Science Based Targets initiative reduction pathway (1.5 °C)",
  },
];

export default function CompliancePage() {
  useDocumentTitle("Compliance Reports");
  const { user, loading } = useAuth();
  const router = useRouter();
  const [selectedReport, setSelectedReport] = useState("");
  const [selectedFramework, setSelectedFramework] =
    useState<Framework>("ghg_protocol");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const resultJson = useMemo(
    () => (result ? JSON.stringify(result, null, 2) : ""),
    [result],
  );

  const reportsQuery = useQuery({
    queryKey: ["reports", user?.company_id],
    queryFn: () => listReports(),
    enabled: !!user && !loading,
  });

  const reports: EmissionReport[] = reportsQuery.data?.items ?? [];

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (reports.length > 0 && !selectedReport) {
      setSelectedReport(reports[0].id);
    }
  }, [reports, selectedReport]);

  async function handleGenerate() {
    if (!selectedReport) return;
    setGenerating(true);
    setResult(null);
    setError("");
    try {
      const res = await generateComplianceReport(
        selectedReport,
        selectedFramework,
      );
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <PageSkeleton />;

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Compliance" },
        ]}
      />
      <h1 className="text-2xl font-bold">Compliance Reports</h1>

      {/* Controls */}
      <div className="card space-y-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs text-[var(--muted)] mb-1">
              Source Report
            </label>
            <select
              value={selectedReport}
              onChange={(e) => setSelectedReport(e.target.value)}
              className="bg-[var(--background)] border border-[var(--card-border)] rounded-md px-3 py-2 text-sm"
            >
              {reports.length === 0 && (
                <option value="">No reports available</option>
              )}
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.year} — {r.total.toLocaleString()} tCO₂e
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating || !selectedReport}
            className="btn-primary"
          >
            {generating ? "Generating..." : "Generate Report"}
          </button>
        </div>

        {/* Framework selector */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {FRAMEWORKS.map((fw) => (
            <button
              key={fw.id}
              onClick={() => {
                setSelectedFramework(fw.id);
                setResult(null);
              }}
              className={`text-left p-3 rounded-lg border transition-colors ${
                selectedFramework === fw.id
                  ? "border-[var(--primary)] bg-[var(--primary)]/10"
                  : "border-[var(--card-border)] hover:border-[var(--muted)]"
              }`}
            >
              <p className="font-semibold text-sm">{fw.label}</p>
              <p className="text-xs text-[var(--muted)] mt-1">{fw.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {error && <div className="text-[var(--danger)]">{error}</div>}

      {/* Result */}
      {result && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              {FRAMEWORKS.find((f) => f.id === selectedFramework)?.label} Report
            </h2>
            <button
              onClick={() => {
                const blob = new Blob([resultJson], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${selectedFramework}_report.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="text-sm text-[var(--primary)] hover:underline"
            >
              Download JSON ↓
            </button>
          </div>
          <pre className="bg-[var(--background)] border border-[var(--card-border)] rounded-lg p-4 text-xs overflow-auto max-h-[600px]">
            {resultJson}
          </pre>
        </div>
      )}
    </div>
  );
}
