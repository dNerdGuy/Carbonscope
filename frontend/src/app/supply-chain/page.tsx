"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  listSuppliers,
  addSupplier,
  getScope3FromSuppliers,
  updateSupplyChainLink,
  deleteSupplyChainLink,
} from "@/lib/api";

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

  const refresh = useCallback(async () => {
    try {
      const [s, sc] = await Promise.all([
        listSuppliers(),
        getScope3FromSuppliers(),
      ]);
      setSuppliers(s);
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
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add");
    } finally {
      setAdding(false);
    }
  }

  async function handleVerify(linkId: string) {
    await updateSupplyChainLink(linkId, "verified");
    await refresh();
  }

  async function handleRemove(linkId: string) {
    await deleteSupplyChainLink(linkId);
    await refresh();
  }

  if (loading) return <div className="p-8 text-[var(--muted)]">Loading...</div>;
  if (error)
    return <div className="p-8 text-[var(--danger)]">Error: {error}</div>;

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <h1 className="text-2xl font-bold">Supply Chain Network</h1>

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
            <label className="block text-xs text-[var(--muted)] mb-1">
              Supplier Company ID
            </label>
            <input
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              required
              className="bg-[var(--background)] border border-[var(--card-border)] rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--muted)] mb-1">
              Annual Spend (USD)
            </label>
            <input
              type="number"
              value={spend}
              onChange={(e) => setSpend(e.target.value)}
              className="bg-[var(--background)] border border-[var(--card-border)] rounded-md px-3 py-2 text-sm w-36"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--muted)] mb-1">
              Category
            </label>
            <select
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
          <p className="text-[var(--muted)] text-sm">
            No suppliers linked yet.
          </p>
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
                      onClick={() => handleRemove(s.link_id)}
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
    </div>
  );
}
