"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  listReports,
  listScenarios,
  createScenario,
  computeScenario,
  deleteScenario,
  type EmissionReport,
  type ScenarioOut,
} from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";

export default function ScenariosPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ScenariosPageInner />
    </Suspense>
  );
}

const ADJUSTMENT_TYPES = [
  {
    key: "energy_switch",
    label: "Renewable Energy Switch",
    description: "Model switching a percentage of energy to renewable sources",
    param: "renewable_pct",
    paramLabel: "Renewable %",
    min: 0,
    max: 100,
    default: 50,
  },
  {
    key: "fleet_electrification",
    label: "Fleet Electrification",
    description: "Model electrifying a percentage of your vehicle fleet",
    param: "electrification_pct",
    paramLabel: "Electrification %",
    min: 0,
    max: 100,
    default: 30,
  },
  {
    key: "supplier_change",
    label: "Supplier Optimization",
    description:
      "Model reducing Scope 3 by switching to lower-emission suppliers",
    param: "scope3_reduction_pct",
    paramLabel: "Scope 3 Reduction %",
    min: 0,
    max: 100,
    default: 20,
  },
  {
    key: "efficiency",
    label: "Operational Efficiency",
    description: "Model general efficiency improvements across Scope 1 & 2",
    param: "efficiency_pct",
    paramLabel: "Efficiency Gain %",
    min: 0,
    max: 50,
    default: 15,
  },
];

function ScenariosPageInner() {
  useDocumentTitle("Scenarios");
  const { user, loading } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const [scenarios, setScenarios] = useState<ScenarioOut[]>([]);
  const [reports, setReports] = useState<EmissionReport[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [statusFilter, setStatusFilter] = useState(
    searchParams.get("status") ?? "",
  );

  // Create form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseReportId, setBaseReportId] = useState("");
  const [adjustments, setAdjustments] = useState<
    Record<string, Record<string, number>>
  >({});
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const fetchData = useCallback(
    async (status?: string) => {
      try {
        const [sRes, rRes] = await Promise.all([
          listScenarios({ status: status || undefined }),
          listReports({ limit: 50 }),
        ]);
        setScenarios(sRes.items);
        setReports(rRes.items);
        if (rRes.items.length > 0) {
          setBaseReportId((prev) => prev || rRes.items[0].id);
        }
        // Sync filter to URL
        const params = new URLSearchParams();
        if (status) params.set("status", status);
        const qs = params.toString();
        router.replace(`/scenarios${qs ? `?${qs}` : ""}`, { scroll: false });
      } catch {
        setError("Failed to load data");
      }
    },
    [router],
  );

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user) fetchData(searchParams.get("status") ?? "");
  }, [user, loading, router, fetchData, searchParams]);

  function toggleAdjustment(key: string, paramKey: string, defaultVal: number) {
    setAdjustments((prev) => {
      const next = { ...prev };
      if (next[key]) {
        delete next[key];
      } else {
        next[key] = { [paramKey]: defaultVal };
      }
      return next;
    });
  }

  function updateAdjustmentValue(key: string, paramKey: string, value: number) {
    setAdjustments((prev) => ({
      ...prev,
      [key]: { ...prev[key], [paramKey]: value },
    }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !baseReportId || Object.keys(adjustments).length === 0) {
      setError(
        "Please provide a name, select a report, and choose at least one adjustment",
      );
      return;
    }
    setCreating(true);
    setError("");
    try {
      const scenario = await createScenario({
        name,
        description: description || undefined,
        base_report_id: baseReportId,
        parameters: adjustments,
      });
      await computeScenario(scenario.id);
      await fetchData(statusFilter);
      setShowCreate(false);
      setName("");
      setDescription("");
      setAdjustments({});
      toast("Scenario created and computed", "success");
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to create scenario",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleCompute(id: string) {
    try {
      await computeScenario(id);
      await fetchData(statusFilter);
      toast("Scenario computed", "success");
    } catch {
      setError("Failed to compute scenario");
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteScenario(id);
      setScenarios((prev) => prev.filter((s) => s.id !== id));
      toast("Scenario deleted", "success");
    } catch {
      setError("Failed to delete");
    } finally {
      setDeleteTarget(null);
    }
  }

  if (loading) return <PageSkeleton />;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Scenarios" },
        ]}
      />
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">What-If Scenarios</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 rounded bg-[var(--primary)] text-black text-sm font-medium hover:opacity-90"
        >
          {showCreate ? "Cancel" : "New Scenario"}
        </button>
      </div>

      {/* Status filter */}
      <div className="flex gap-3 mb-4">
        <select
          aria-label="Filter by status"
          value={statusFilter}
          onChange={(e) => {
            const val = e.target.value;
            setStatusFilter(val);
            fetchData(val);
          }}
          className="input text-sm px-3 py-1.5 w-48"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="computed">Computed</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-red-900/20 border border-red-800 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-6 mb-6"
        >
          <h2 className="text-lg font-semibold mb-4">Create Scenario</h2>

          <div className="grid gap-4 md:grid-cols-2 mb-4">
            <div>
              <label className="block text-sm text-[var(--muted)] mb-1">
                Scenario Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded border border-[var(--card-border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
                placeholder="e.g., 100% Renewable by 2030"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-[var(--muted)] mb-1">
                Base Report
              </label>
              <select
                value={baseReportId}
                onChange={(e) => setBaseReportId(e.target.value)}
                className="w-full rounded border border-[var(--card-border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
              >
                {reports.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.year} — {r.total.toLocaleString()} tCO2e
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-sm text-[var(--muted)] mb-1">
              Description (optional)
            </label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded border border-[var(--card-border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:border-[var(--primary)]"
            />
          </div>

          <h3 className="text-sm font-semibold mb-3">Adjustments</h3>
          <div className="grid gap-3 md:grid-cols-2 mb-4">
            {ADJUSTMENT_TYPES.map((adj) => {
              const active = !!adjustments[adj.key];
              return (
                <button
                  type="button"
                  key={adj.key}
                  className={`rounded border p-4 text-left transition-colors ${
                    active
                      ? "border-[var(--primary)] bg-green-900/10"
                      : "border-[var(--card-border)] bg-[var(--background)]/50"
                  }`}
                  role="checkbox"
                  aria-checked={active}
                  onClick={() =>
                    toggleAdjustment(adj.key, adj.param, adj.default)
                  }
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">{adj.label}</span>
                    <span
                      className={`w-4 h-4 rounded border ${active ? "bg-[var(--primary)] border-[var(--primary)]" : "border-[var(--card-border)]"}`}
                    />
                  </div>
                  <p className="text-xs text-[var(--muted)]">
                    {adj.description}
                  </p>
                  {active && (
                    <div className="mt-3" onClick={(e) => e.stopPropagation()}>
                      <label className="text-xs text-[var(--muted)]">
                        {adj.paramLabel}:{" "}
                        {adjustments[adj.key]?.[adj.param] ?? adj.default}%
                      </label>
                      <input
                        type="range"
                        min={adj.min}
                        max={adj.max}
                        value={adjustments[adj.key]?.[adj.param] ?? adj.default}
                        onChange={(e) =>
                          updateAdjustmentValue(
                            adj.key,
                            adj.param,
                            Number(e.target.value),
                          )
                        }
                        className="w-full mt-1 accent-[var(--primary)]"
                      />
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          <button
            type="submit"
            disabled={creating}
            className="px-6 py-2 rounded bg-[var(--primary)] text-black font-medium hover:opacity-90 disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create & Compute"}
          </button>
        </form>
      )}

      {/* Scenario list */}
      <div className="space-y-4">
        {scenarios.length === 0 && !showCreate ? (
          <div className="text-center py-16 rounded-xl border border-[var(--card-border)] bg-[var(--card)]">
            <span className="text-4xl mb-3 block">🔬</span>
            <p className="text-[var(--muted)] mb-2">No scenarios yet</p>
            <p className="text-sm text-[var(--muted)]">
              Create one to model emission reduction strategies.
            </p>
          </div>
        ) : (
          scenarios.map((s) => {
            const results = s.results as Record<string, unknown> | null;
            const totalBaseline = (results?.total_baseline as number) || 0;
            const totalAdjusted = (results?.total_adjusted as number) || 0;
            const reductionPct = (results?.reduction_pct as number) || 0;
            const totalReduction = (results?.total_reduction as number) || 0;

            return (
              <div
                key={s.id}
                className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold">{s.name}</h3>
                    {s.description && (
                      <p className="text-sm text-[var(--muted)]">
                        {s.description}
                      </p>
                    )}
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded font-medium ${
                      s.status === "computed"
                        ? "bg-green-900/30 text-green-400"
                        : "bg-yellow-900/30 text-yellow-400"
                    }`}
                  >
                    {s.status}
                  </span>
                </div>

                {s.status === "computed" && results && (
                  <div className="grid grid-cols-3 gap-4 mb-3">
                    <div className="text-center">
                      <p className="text-xs text-[var(--muted)]">Baseline</p>
                      <p className="text-lg font-bold">
                        {totalBaseline.toLocaleString()}
                      </p>
                      <p className="text-xs text-[var(--muted)]">tCO2e</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-[var(--muted)]">Adjusted</p>
                      <p className="text-lg font-bold text-blue-400">
                        {totalAdjusted.toLocaleString()}
                      </p>
                      <p className="text-xs text-[var(--muted)]">tCO2e</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-[var(--muted)]">Reduction</p>
                      <p className="text-lg font-bold text-green-400">
                        -{totalReduction.toLocaleString()} (
                        {reductionPct.toFixed(1)}%)
                      </p>
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  {s.status === "draft" && (
                    <button
                      onClick={() => handleCompute(s.id)}
                      className="px-3 py-1.5 rounded bg-blue-800/50 text-blue-300 text-sm font-medium hover:bg-blue-800/70"
                    >
                      Compute
                    </button>
                  )}
                  <button
                    onClick={() => setDeleteTarget(s.id)}
                    className="px-3 py-1.5 rounded border border-[var(--card-border)] text-sm text-[var(--muted)] hover:text-[var(--danger)]"
                  >
                    Delete
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Scenario"
        message="This scenario and its results will be permanently removed. Continue?"
        confirmLabel="Delete"
        variant="danger"
        onConfirm={() => deleteTarget && handleDelete(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
