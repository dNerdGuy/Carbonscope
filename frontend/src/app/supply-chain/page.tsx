"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Breadcrumbs from "@/components/Breadcrumbs";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  listSuppliers,
  addSupplier,
  getScope3FromSuppliers,
  updateSupplyChainLink,
  deleteSupplyChainLink,
} from "@/lib/api";
import { PageSkeleton } from "@/components/Skeleton";
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

export default function SupplyChainPage() {
  useDocumentTitle("Supply Chain");
  const { user, loading } = useAuth();
  const router = useRouter();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [scope3, setScope3] = useState<Scope3Summary | null>(null);
  const [error, setError] = useState("");

  // Add supplier form
  const [supplierId, setSupplierId] = useState("");
  const [spend, setSpend] = useState("");
  const [category, setCategory] = useState("general");
  const [adding, setAdding] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const { toast } = useToast();

  const refresh = useCallback(async () => {
    try {
      const [s, sc] = await Promise.all([
        listSuppliers(),
        getScope3FromSuppliers(),
      ]);
      setSuppliers(s.items);
      setScope3(sc);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user) refresh();
  }, [user, loading, router, refresh]);

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
      await refresh();
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
      await refresh();
      toast("Supplier verified", "success");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to verify");
    }
  }

  async function handleRemove(linkId: string) {
    try {
      await deleteSupplyChainLink(linkId);
      await refresh();
      toast("Supplier removed", "success");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to remove");
    } finally {
      setDeleteTarget(null);
    }
  }

  if (loading) return <PageSkeleton />;
  if (error && suppliers.length === 0)
    return <div className="p-8 text-[var(--danger)]">Error: {error}</div>;

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Supply Chain" },
        ]}
      />
      <h1 className="text-2xl font-bold">Supply Chain Network</h1>

      {error && (
        <div className="bg-[var(--danger)]/10 border border-[var(--danger)] text-[var(--danger)] px-4 py-2 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Scope 3 from suppliers summary */}
      {scope3 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <p className="text-[var(--muted)] text-sm">Scope 3 (Cat 1)</p>
            <p className="text-xl font-bold text-[var(--scope3)]">
              {scope3.scope3_cat1_from_suppliers.toLocaleString()} tCO₂e
            </p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-sm">Suppliers</p>
            <p className="text-xl font-bold">{scope3.supplier_count}</p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-sm">Verified</p>
            <p className="text-xl font-bold text-[var(--primary)]">
              {scope3.verified_count}
            </p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-sm">Coverage</p>
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
              className="bg-[var(--background)] border border-[var(--card-border)] rounded-md px-3 py-2 text-sm"
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
              className="bg-[var(--background)] border border-[var(--card-border)] rounded-md px-3 py-2 text-sm w-36"
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
              className="bg-[var(--background)] border border-[var(--card-border)] rounded-md px-3 py-2 text-sm"
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
            <p className="text-[var(--muted)] mb-2">No suppliers linked yet</p>
            <p className="text-sm text-[var(--muted)]">
              Add a supplier above to start tracking Scope 3 emissions.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--muted)] text-left border-b border-[var(--card-border)]">
                <th className="pb-2">Company</th>
                <th className="pb-2">Industry</th>
                <th className="pb-2">Category</th>
                <th className="pb-2">Spend</th>
                <th className="pb-2">Emissions</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr
                  key={s.link_id}
                  className="border-b border-[var(--card-border)]"
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
                          ? "bg-green-900/30 text-green-400"
                          : s.status === "rejected"
                            ? "bg-red-900/30 text-red-400"
                            : "bg-yellow-900/30 text-yellow-400"
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
