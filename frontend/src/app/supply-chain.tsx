import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  listSuppliers,
  addSupplier,
  getScope3FromSuppliers,
  updateSupplyChainLink,
  deleteSupplyChainLink,
} from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
import { StatusMessage } from "@/components/StatusMessage";
import { useToast } from "@/components/Toast";

interface Supplier {
  link_id: string;
  company_id: string;
  company_name: string;
  industry: string;
  region: string;
  spend_usd: number | null;
  category: string;
  status: string;
  emissions: {
    scope1: number | null;
    scope2: number | null;
    total: number | null;
    confidence: number | null;
    year: number | null;
  } | null;
  created_at: string;
}

interface Scope3Summary {
  scope3_cat1_from_suppliers: number;
  supplier_count: number;
  verified_count: number;
  coverage_pct: number;
}

export const Route = createFileRoute("/supply-chain")({
  component: SupplyChainPage,
});

function SupplyChainPage() {
  useDocumentTitle("Supply Chain");
  const { user, loading } = useRequireAuth();
  const [error, setError] = useState("");

  // Add supplier form
  const [supplierId, setSupplierId] = useState("");
  const [spend, setSpend] = useState("");
  const [category, setCategory] = useState("general");
  const [adding, setAdding] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const { toast } = useToast();

  const supplyQuery = useQuery<[{ items: Supplier[] }, Scope3Summary]>({
    queryKey: ["supply-chain", user?.company_id],
    queryFn: () => Promise.all([listSuppliers(), getScope3FromSuppliers()]),
    enabled: !!user && !loading,
  });

  const suppliers = supplyQuery.data?.[0]?.items ?? [];
  const scope3 = supplyQuery.data?.[1] ?? null;

  useEffect(() => {
    if (supplyQuery.error) {
      setError(
        supplyQuery.error instanceof Error
          ? supplyQuery.error.message
          : "Failed to load",
      );
    }
  }, [supplyQuery.error]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    try {
      await addSupplier({
        supplier_company_id: supplierId,
        spend_usd: spend ? parseFloat(spend) : undefined,
        category,
      });
      setSupplierId("");
      setSpend("");
      setCategory("general");
      await supplyQuery.refetch();
      toast("Supplier added successfully", "success");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add");
    } finally {
      setAdding(false);
    }
  }

  async function handleVerify(linkId: string) {
    try {
      await updateSupplyChainLink(linkId, "verified");
      await supplyQuery.refetch();
      toast("Supplier verified", "success");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to verify");
    }
  }

  async function handleRemove(linkId: string) {
    try {
      await deleteSupplyChainLink(linkId);
      await supplyQuery.refetch();
      toast("Supplier removed", "success");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to remove");
    } finally {
      setDeleteTarget(null);
    }
  }

  if (loading || supplyQuery.isLoading) return <PageSkeleton />;
  if (error && suppliers.length === 0)
    return (
      <div className="p-8">
        <StatusMessage message={error} variant="error" />
      </div>
    );

  return (
    <div className="max-w-6xl mx-auto p-8 animate-fade-up space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Supply Chain" },
        ]}
      />
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">
        Supply Chain Network
      </h1>

      {error && <StatusMessage message={error} variant="error" />}

      {/* Scope 3 from suppliers summary */}
      {scope3 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
              Scope 3 (Cat 1)
            </p>
            <p className="text-xl font-bold text-[var(--scope3)]">
              {scope3.scope3_cat1_from_suppliers.toLocaleString()} tCO₂e
            </p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
              Suppliers
            </p>
            <p className="text-xl font-bold">{scope3.supplier_count}</p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
              Verified
            </p>
            <p className="text-xl font-bold text-[var(--primary)]">
              {scope3.verified_count}
            </p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
              Coverage
            </p>
            <p className="text-xl font-bold">
              {scope3.coverage_pct.toFixed(0)}%
            </p>
          </div>
        </div>
      )}

      {/* Add Supplier */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Add Supplier</h2>
        <form onSubmit={handleAdd} className="flex flex-wrap gap-3 items-end">
          <div>
            <label
              htmlFor="supplier-company-id"
              className="block text-xs text-[var(--muted)] mb-1"
            >
              Supplier Company ID
            </label>
            <input
              id="supplier-company-id"
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              required
              placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
              pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
              title="Enter a valid UUID for the supplier company"
              className="input text-sm"
            />
          </div>
          <div>
            <label
              htmlFor="supplier-spend"
              className="block text-xs text-[var(--muted)] mb-1"
            >
              Annual Spend (USD)
            </label>
            <input
              id="supplier-spend"
              type="number"
              value={spend}
              onChange={(e) => setSpend(e.target.value)}
              min={0}
              step="any"
              className="input text-sm w-36"
            />
          </div>
          <div>
            <label
              htmlFor="supplier-category"
              className="block text-xs text-[var(--muted)] mb-1"
            >
              Category
            </label>
            <select
              id="supplier-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="input text-sm"
            >
              <option value="general">General</option>
              <option value="raw_materials">Raw Materials</option>
              <option value="logistics">Logistics</option>
              <option value="services">Services</option>
              <option value="energy">Energy</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={adding}
            className="btn-primary h-[38px]"
          >
            {adding ? "Adding..." : "Add Supplier"}
          </button>
        </form>
      </div>

      {/* Suppliers table */}
      <div className="card overflow-x-auto">
        <h2 className="text-lg font-semibold mb-4">Suppliers</h2>
        {suppliers.length === 0 ? (
          <div className="text-center py-12">
            <span className="text-4xl mb-3 block">🔗</span>
            <p className="text-[var(--muted)] text-base font-medium mb-8 max-w-2xl">
              No suppliers linked yet
            </p>
            <p className="text-sm text-[var(--muted)]">
              Add a supplier above to start tracking Scope 3 emissions.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--muted)] text-left border-b border-[var(--card-border)]/50">
                <th className="pb-2 text-[var(--muted)] text-xs font-semibold uppercase tracking-wider">
                  Company
                </th>
                <th className="pb-2 text-[var(--muted)] text-xs font-semibold uppercase tracking-wider">
                  Industry
                </th>
                <th className="pb-2 text-[var(--muted)] text-xs font-semibold uppercase tracking-wider">
                  Category
                </th>
                <th className="pb-2 text-[var(--muted)] text-xs font-semibold uppercase tracking-wider">
                  Spend
                </th>
                <th className="pb-2 text-[var(--muted)] text-xs font-semibold uppercase tracking-wider">
                  Emissions
                </th>
                <th className="pb-2 text-[var(--muted)] text-xs font-semibold uppercase tracking-wider">
                  Status
                </th>
                <th className="pb-2 text-[var(--muted)] text-xs font-semibold uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr
                  key={s.link_id}
                  className="border-b border-[var(--card-border)]/50"
                >
                  <td className="py-2 font-medium">{s.company_name}</td>
                  <td className="py-2">{s.industry}</td>
                  <td className="py-2">{s.category}</td>
                  <td className="py-2">
                    {s.spend_usd ? `$${(s.spend_usd / 1000).toFixed(0)}k` : "—"}
                  </td>
                  <td className="py-2">
                    {s.emissions?.total
                      ? `${s.emissions.total.toLocaleString()} tCO₂e`
                      : "—"}
                  </td>
                  <td className="py-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        s.status === "verified"
                          ? "badge-success"
                          : s.status === "rejected"
                            ? "badge-danger"
                            : "badge-warning"
                      }`}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="py-2 space-x-2">
                    {s.status === "pending" && (
                      <button
                        onClick={() => handleVerify(s.link_id)}
                        className="text-xs text-[var(--primary)] hover:underline"
                      >
                        Verify
                      </button>
                    )}
                    <button
                      onClick={() => setDeleteTarget(s.link_id)}
                      className="text-xs text-[var(--danger)] hover:underline"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Remove Supplier"
        message="This will remove the supply chain link. Continue?"
        confirmLabel="Remove"
        variant="danger"
        onConfirm={() => deleteTarget && handleRemove(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
