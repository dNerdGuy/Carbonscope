"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import { PageSkeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  listPortfolios,
  createPortfolio,
  getPortfolioSummary,
  listPortfolioAssets,
  addPortfolioAsset,
  deletePortfolioAsset,
  type FinancedPortfolio,
  type FinancedAsset,
  type PortfolioSummary,
} from "@/lib/api";

export default function PCAFPage() {
  useDocumentTitle("PCAF Portfolios");
  const { user, loading } = useAuth();
  const router = useRouter();
  const [portfolios, setPortfolios] = useState<FinancedPortfolio[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [assets, setAssets] = useState<FinancedAsset[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newYear, setNewYear] = useState(new Date().getFullYear());

  // Asset form
  const [showAssetForm, setShowAssetForm] = useState(false);
  const [deleteAssetId, setDeleteAssetId] = useState<string | null>(null);
  const [assetForm, setAssetForm] = useState({
    asset_name: "",
    asset_class: "corporate_bonds",
    outstanding_amount: 0,
    total_equity_debt: 0,
    investee_emissions_tco2e: 0,
    data_quality_score: 3,
  });

  const fetchPortfolios = useCallback(async () => {
    try {
      const data = await listPortfolios();
      setPortfolios(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load portfolios");
    }
  }, []);

  const fetchPortfolioDetails = useCallback(async (id: string) => {
    try {
      const [s, a] = await Promise.all([
        getPortfolioSummary(id),
        listPortfolioAssets(id),
      ]);
      setSummary(s);
      setAssets(a.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load portfolio");
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    if (user) fetchPortfolios();
  }, [user, loading, router, fetchPortfolios]);

  useEffect(() => {
    if (selectedId) fetchPortfolioDetails(selectedId);
  }, [selectedId, fetchPortfolioDetails]);

  const handleCreate = async () => {
    try {
      const p = await createPortfolio({ name: newName, year: newYear });
      setPortfolios((prev) => [p, ...prev]);
      setShowCreate(false);
      setNewName("");
      setSelectedId(p.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create portfolio");
    }
  };

  const handleAddAsset = async () => {
    if (!selectedId) return;
    try {
      const a = await addPortfolioAsset(selectedId, assetForm);
      setAssets((prev) => [a, ...prev]);
      setShowAssetForm(false);
      fetchPortfolioDetails(selectedId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add asset");
    }
  };

  const handleDeleteAsset = async (assetId: string) => {
    if (!selectedId) return;
    try {
      await deletePortfolioAsset(selectedId, assetId);
      setAssets((prev) => prev.filter((a) => a.id !== assetId));
      fetchPortfolioDetails(selectedId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete asset");
    } finally {
      setDeleteAssetId(null);
    }
  };

  if (loading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">PCAF Financed Emissions</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-white hover:bg-emerald-700"
        >
          New Portfolio
        </button>
      </div>

      {error && <p className="mb-4 text-red-400">{error}</p>}

      {showCreate && (
        <div className="mb-6 rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4">
          <h3 className="mb-2 font-semibold">Create Portfolio</h3>
          <div className="flex gap-4">
            <input
              className="input"
              placeholder="Portfolio name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              aria-label="Portfolio name"
            />
            <input
              type="number"
              className="w-24 input"
              value={newYear}
              onChange={(e) => setNewYear(Number(e.target.value))}
              aria-label="Portfolio year"
            />
            <button
              onClick={handleCreate}
              className="rounded bg-emerald-600 px-4 py-2 text-white"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="text-[var(--muted)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Portfolio list */}
        <div className="space-y-2">
          <h2 className="mb-2 text-lg font-semibold text-[var(--foreground)]">
            Portfolios
          </h2>
          {portfolios.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelectedId(p.id)}
              className={`w-full rounded-lg border p-3 text-left ${
                selectedId === p.id
                  ? "border-emerald-500 bg-emerald-900/20"
                  : "border-[var(--card-border)] bg-[var(--card)] hover:border-[var(--muted)]"
              }`}
            >
              <p className="font-medium">{p.name}</p>
              <p className="text-sm text-[var(--muted)]">Year: {p.year}</p>
            </button>
          ))}
          {portfolios.length === 0 && (
            <p className="text-[var(--muted)]">
              No portfolios yet. Create one to get started.
            </p>
          )}
        </div>

        {/* Portfolio details */}
        <div className="lg:col-span-2">
          {summary ? (
            <div>
              <div className="mb-4 grid grid-cols-3 gap-4">
                <div className="rounded-lg bg-[var(--card)] p-4">
                  <p className="text-sm text-[var(--muted)]">
                    Total Financed Emissions
                  </p>
                  <p className="text-2xl font-bold text-emerald-400">
                    {summary.total_financed_emissions.toLocaleString()} tCO₂e
                  </p>
                </div>
                <div className="rounded-lg bg-[var(--card)] p-4">
                  <p className="text-sm text-[var(--muted)]">
                    Weighted Data Quality
                  </p>
                  <p className="text-2xl font-bold">
                    {summary.weighted_data_quality.toFixed(1)}/5
                  </p>
                </div>
                <div className="rounded-lg bg-[var(--card)] p-4">
                  <p className="text-sm text-[var(--muted)]">Assets</p>
                  <p className="text-2xl font-bold">{summary.asset_count}</p>
                </div>
              </div>

              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold">Assets</h3>
                <button
                  onClick={() => setShowAssetForm(true)}
                  className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
                >
                  Add Asset
                </button>
              </div>

              {showAssetForm && (
                <div className="mb-4 rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-4">
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      className="input"
                      placeholder="Asset name"
                      onChange={(e) =>
                        setAssetForm({
                          ...assetForm,
                          asset_name: e.target.value,
                        })
                      }
                      aria-label="Asset name"
                    />
                    <select
                      className="input"
                      onChange={(e) =>
                        setAssetForm({
                          ...assetForm,
                          asset_class: e.target.value,
                        })
                      }
                      aria-label="Asset class"
                    >
                      <option value="corporate_bonds">Corporate Bonds</option>
                      <option value="listed_equity">Listed Equity</option>
                      <option value="business_loans">Business Loans</option>
                      <option value="project_finance">Project Finance</option>
                      <option value="mortgages">Mortgages</option>
                    </select>
                    <input
                      type="number"
                      className="input"
                      placeholder="Outstanding amount"
                      onChange={(e) =>
                        setAssetForm({
                          ...assetForm,
                          outstanding_amount: Number(e.target.value),
                        })
                      }
                      aria-label="Outstanding amount"
                    />
                    <input
                      type="number"
                      className="input"
                      placeholder="Total equity/debt"
                      onChange={(e) =>
                        setAssetForm({
                          ...assetForm,
                          total_equity_debt: Number(e.target.value),
                        })
                      }
                      aria-label="Total equity or debt"
                    />
                    <input
                      type="number"
                      className="input"
                      placeholder="Investee emissions (tCO₂e)"
                      onChange={(e) =>
                        setAssetForm({
                          ...assetForm,
                          investee_emissions_tco2e: Number(e.target.value),
                        })
                      }
                      aria-label="Investee emissions in tCO2e"
                    />
                    <select
                      className="input"
                      onChange={(e) =>
                        setAssetForm({
                          ...assetForm,
                          data_quality_score: Number(e.target.value),
                        })
                      }
                      aria-label="Data quality score"
                    >
                      {[1, 2, 3, 4, 5].map((s) => (
                        <option key={s} value={s}>
                          Quality Score: {s}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={handleAddAsset}
                      className="rounded bg-emerald-600 px-4 py-2 text-white"
                    >
                      Add
                    </button>
                    <button
                      onClick={() => setShowAssetForm(false)}
                      className="text-[var(--muted)]"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                {assets.map((a) => (
                  <div
                    key={a.id}
                    className="flex items-center justify-between rounded-lg border border-[var(--card-border)] bg-[var(--card)] p-3"
                  >
                    <div>
                      <p className="font-medium">{a.asset_name}</p>
                      <p className="text-sm text-[var(--muted)]">
                        {a.asset_class} · $
                        {a.outstanding_amount.toLocaleString()} ·{" "}
                        {a.financed_emissions_tco2e.toFixed(1)} tCO₂e
                      </p>
                    </div>
                    <button
                      onClick={() => setDeleteAssetId(a.id)}
                      className="text-red-400 hover:text-red-300"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-[var(--muted)]">
              Select a portfolio to view details.
            </p>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={!!deleteAssetId}
        title="Delete Asset"
        message="Are you sure you want to delete this asset? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={() => deleteAssetId && handleDeleteAsset(deleteAssetId)}
        onCancel={() => setDeleteAssetId(null)}
      />
    </main>
  );
}
