import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PageSkeleton } from "@/components/Skeleton";
import ConfirmDialog from "@/components/ConfirmDialog";
import { StatusMessage } from "@/components/StatusMessage";
import Breadcrumbs from "@/components/Breadcrumbs";
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

export const Route = createFileRoute("/pcaf")({ component: PCAFPage });

function PCAFPage() {
  useDocumentTitle("PCAF Portfolios");
  const { user, loading } = useRequireAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);
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

  const portfoliosQuery = useQuery<{ items: FinancedPortfolio[] }>({
    queryKey: ["pcaf-portfolios", user?.company_id],
    queryFn: () => listPortfolios(),
    enabled: !!user && !loading,
  });

  const portfolios = portfoliosQuery.data?.items ?? [];

  const detailsQuery = useQuery<[PortfolioSummary, { items: FinancedAsset[] }]>(
    {
      queryKey: ["pcaf-details", selectedId],
      queryFn: () =>
        Promise.all([
          getPortfolioSummary(selectedId!),
          listPortfolioAssets(selectedId!),
        ]),
      enabled: !!selectedId,
    },
  );

  const summary = detailsQuery.data?.[0] ?? null;
  const assets = detailsQuery.data?.[1]?.items ?? [];

  useEffect(() => {
    if (portfoliosQuery.error) {
      setError(
        portfoliosQuery.error instanceof Error
          ? portfoliosQuery.error.message
          : "Failed to load portfolios",
      );
    }
  }, [portfoliosQuery.error]);

  const handleCreate = async () => {
    try {
      const p = await createPortfolio({ name: newName, year: newYear });
      await portfoliosQuery.refetch();
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
      await addPortfolioAsset(selectedId, assetForm);
      setShowAssetForm(false);
      await detailsQuery.refetch();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add asset");
    }
  };

  const handleDeleteAsset = async (assetId: string) => {
    if (!selectedId) return;
    try {
      await deletePortfolioAsset(selectedId, assetId);
      await detailsQuery.refetch();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete asset");
    } finally {
      setDeleteAssetId(null);
    }
  };

  if (loading || portfoliosQuery.isLoading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[{ label: "Dashboard", href: "/dashboard" }, { label: "PCAF" }]}
      />
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-extrabold tracking-tight mb-2">
          PCAF Financed Emissions
        </h1>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          New Portfolio
        </button>
      </div>

      {error && <StatusMessage message={error} variant="error" />}

      {showCreate && (
        <div className="mb-6 card ">
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
            <button onClick={handleCreate} className="btn-primary">
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
                  ? "border-[var(--primary)] bg-[var(--primary)]/10"
                  : "border-[var(--card-border)] bg-[var(--card)] hover:border-[var(--muted)]"
              }`}
            >
              <p className="font-medium">{p.name}</p>
              <p className="text-sm text-[var(--muted)]">Year: {p.year}</p>
            </button>
          ))}
          {portfolios.length === 0 && (
            <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
              No portfolios yet. Create one to get started.
            </p>
          )}
        </div>

        {/* Portfolio details */}
        <div className="lg:col-span-2">
          {summary ? (
            <div>
              <div className="mb-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-lg bg-[var(--card)] p-4">
                  <p className="text-sm text-[var(--muted)]">
                    Total Financed Emissions
                  </p>
                  <p className="text-2xl font-bold text-[var(--primary)]">
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
                  className="btn-primary text-sm px-3 py-1"
                >
                  Add Asset
                </button>
              </div>

              {showAssetForm && (
                <div className="mb-4 card ">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label
                        htmlFor="asset-name"
                        className="block text-xs text-[var(--muted)] mb-1"
                      >
                        Asset Name
                      </label>
                      <input
                        id="asset-name"
                        className="input w-full"
                        placeholder="Asset name"
                        onChange={(e) =>
                          setAssetForm({
                            ...assetForm,
                            asset_name: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="asset-class"
                        className="block text-xs text-[var(--muted)] mb-1"
                      >
                        Asset Class
                      </label>
                      <select
                        id="asset-class"
                        className="input w-full"
                        onChange={(e) =>
                          setAssetForm({
                            ...assetForm,
                            asset_class: e.target.value,
                          })
                        }
                      >
                        <option value="corporate_bonds">Corporate Bonds</option>
                        <option value="listed_equity">Listed Equity</option>
                        <option value="business_loans">Business Loans</option>
                        <option value="project_finance">Project Finance</option>
                        <option value="mortgages">Mortgages</option>
                      </select>
                    </div>
                    <div>
                      <label
                        htmlFor="outstanding-amount"
                        className="block text-xs text-[var(--muted)] mb-1"
                      >
                        Outstanding Amount
                      </label>
                      <input
                        id="outstanding-amount"
                        type="number"
                        className="input w-full"
                        placeholder="0"
                        onChange={(e) =>
                          setAssetForm({
                            ...assetForm,
                            outstanding_amount: Number(e.target.value),
                          })
                        }
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="total-equity-debt"
                        className="block text-xs text-[var(--muted)] mb-1"
                      >
                        Total Equity/Debt
                      </label>
                      <input
                        id="total-equity-debt"
                        type="number"
                        className="input w-full"
                        placeholder="0"
                        onChange={(e) =>
                          setAssetForm({
                            ...assetForm,
                            total_equity_debt: Number(e.target.value),
                          })
                        }
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="investee-emissions"
                        className="block text-xs text-[var(--muted)] mb-1"
                      >
                        Investee Emissions (tCO₂e)
                      </label>
                      <input
                        id="investee-emissions"
                        type="number"
                        className="input w-full"
                        placeholder="0"
                        onChange={(e) =>
                          setAssetForm({
                            ...assetForm,
                            investee_emissions_tco2e: Number(e.target.value),
                          })
                        }
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="data-quality"
                        className="block text-xs text-[var(--muted)] mb-1"
                      >
                        Data Quality Score
                      </label>
                      <select
                        id="data-quality"
                        className="input w-full"
                        onChange={(e) =>
                          setAssetForm({
                            ...assetForm,
                            data_quality_score: Number(e.target.value),
                          })
                        }
                      >
                        {[1, 2, 3, 4, 5].map((s) => (
                          <option key={s} value={s}>
                            Quality Score: {s}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button onClick={handleAddAsset} className="btn-primary">
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
                      className="text-[var(--danger)] hover:opacity-80"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
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
    </div>
  );
}
