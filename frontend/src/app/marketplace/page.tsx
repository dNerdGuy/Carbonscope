"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import ConfirmDialog from "@/components/ConfirmDialog";
import { PageSkeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import {
  browseListings,
  purchaseListing,
  createListing,
  listReports,
  type DataListingOut,
  type PaginatedResponse,
  type EmissionReport,
  ApiError,
} from "@/lib/api";

export default function MarketplacePage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <MarketplacePageInner />
    </Suspense>
  );
}

function MarketplacePageInner() {
  useDocumentTitle("Data Marketplace");
  const { user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [data, setData] = useState<PaginatedResponse<DataListingOut> | null>(
    null,
  );
  const [error, setError] = useState("");
  const [industry, setIndustry] = useState(searchParams.get("industry") ?? "");
  const [region, setRegion] = useState(searchParams.get("region") ?? "");

  // Create listing state
  const [showCreate, setShowCreate] = useState(false);
  const [reports, setReports] = useState<EmissionReport[]>([]);
  const [createForm, setCreateForm] = useState({
    title: "",
    description: "",
    data_type: "emission_report",
    report_id: "",
    price_credits: 0,
  });
  const [creating, setCreating] = useState(false);
  const [purchaseTarget, setPurchaseTarget] = useState<string | null>(null);

  const fetchListings = useCallback(
    async (ind?: string, reg?: string) => {
      try {
        const res = await browseListings({
          industry: ind || undefined,
          region: reg || undefined,
          limit: 50,
        });
        setData(res);
        // Sync filters to URL
        const params = new URLSearchParams();
        if (ind) params.set("industry", ind);
        if (reg) params.set("region", reg);
        const qs = params.toString();
        router.replace(`/marketplace${qs ? `?${qs}` : ""}`, { scroll: false });
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load listings");
      }
    },
    [router],
  );

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (user)
      fetchListings(
        searchParams.get("industry") ?? "",
        searchParams.get("region") ?? "",
      );
  }, [user, loading, router, fetchListings, searchParams]);

  async function handlePurchase(id: string) {
    setPurchaseTarget(null);
    try {
      await purchaseListing(id);
      toast("Purchase successful!", "success");
      await fetchListings();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Purchase failed");
    }
  }

  async function openCreate() {
    setShowCreate(true);
    try {
      const r = await listReports({ limit: 100 });
      setReports(r.items);
    } catch {
      // ignore — user may not have reports
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!createForm.report_id || !createForm.title) return;
    setCreating(true);
    setError("");
    try {
      await createListing({
        title: createForm.title,
        description: createForm.description || undefined,
        data_type: createForm.data_type,
        report_id: createForm.report_id,
        price_credits: createForm.price_credits,
      });
      setShowCreate(false);
      setCreateForm({
        title: "",
        description: "",
        data_type: "emission_report",
        report_id: "",
        price_credits: 0,
      });
      await fetchListings();
      toast("Listing created successfully", "success");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create listing");
    } finally {
      setCreating(false);
    }
  }

  if (loading || (!data && !error)) {
    return <PageSkeleton />;
  }

  if (error && !data) {
    return <div className="p-8 text-[var(--danger)]">Error: {error}</div>;
  }

  const listings = data?.items ?? [];

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Data Marketplace</h1>
          <p className="text-[var(--muted)]">
            Browse and purchase anonymized emission data from other
            organizations.
          </p>
        </div>
        <button className="btn-primary text-sm px-4 py-2" onClick={openCreate}>
          + Create Listing
        </button>
      </div>

      <div className="flex gap-3">
        <Link
          href="/marketplace/seller"
          className="btn-secondary text-sm px-4 py-2"
        >
          📊 Seller Dashboard
        </Link>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-[var(--danger)]/10 text-[var(--danger)] text-sm">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div>
          <label htmlFor="filter-industry" className="sr-only">Filter by industry</label>
          <input
            id="filter-industry"
            type="text"
            placeholder="Filter by industry..."
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="input text-sm px-3 py-1.5 w-48"
          />
        </div>
        <div>
          <label htmlFor="filter-region" className="sr-only">Filter by region</label>
          <input
            id="filter-region"
            type="text"
            placeholder="Filter by region..."
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            className="input text-sm px-3 py-1.5 w-48"
          />
        </div>
        <button
          onClick={() => fetchListings(industry, region)}
          className="text-sm px-4 py-1.5 rounded-md bg-[var(--card-border)] hover:bg-[var(--primary)] hover:text-black transition-colors"
        >
          Apply
        </button>
        <span className="text-sm text-[var(--muted)] self-center">
          {data?.total ?? 0} listing{data?.total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold mb-4">Create New Listing</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label htmlFor="listing-title" className="label">
                Title
              </label>
              <input
                id="listing-title"
                className="input w-full"
                value={createForm.title}
                onChange={(e) =>
                  setCreateForm({ ...createForm, title: e.target.value })
                }
                required
              />
            </div>
            <div>
              <label htmlFor="listing-description" className="label">
                Description
              </label>
              <input
                id="listing-description"
                className="input w-full"
                value={createForm.description}
                onChange={(e) =>
                  setCreateForm({ ...createForm, description: e.target.value })
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="listing-report" className="label">
                  Report
                </label>
                <select
                  id="listing-report"
                  className="input w-full"
                  value={createForm.report_id}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, report_id: e.target.value })
                  }
                  required
                >
                  <option value="">Select a report...</option>
                  {reports.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.year} — {r.total.toFixed(1)} tCO₂e
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="listing-price" className="label">
                  Price (Credits)
                </label>
                <input
                  id="listing-price"
                  type="number"
                  className="input w-full"
                  min={0}
                  value={createForm.price_credits}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      price_credits: parseInt(e.target.value) || 0,
                    })
                  }
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                className="btn-primary text-sm px-4 py-2"
                disabled={creating}
              >
                {creating ? "Creating..." : "Create Listing"}
              </button>
              <button
                type="button"
                className="text-sm px-4 py-2 text-[var(--muted)] hover:text-[var(--foreground)]"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Listings Grid */}
      {listings.length === 0 ? (
        <div className="card p-12 text-center text-[var(--muted)]">
          <p className="text-4xl mb-3">🏪</p>
          <p>No listings available yet.</p>
          <p className="text-sm mt-1">
            Create the first listing to share anonymized emission data.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {listings.map((listing) => (
            <div key={listing.id} className="card p-5 flex flex-col">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--primary)]/20 text-[var(--primary)] font-medium">
                    {listing.data_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-[var(--muted)]">
                    {listing.year}
                  </span>
                </div>
                <h3 className="font-semibold mb-1">{listing.title}</h3>
                {listing.description && (
                  <p className="text-sm text-[var(--muted)] mb-2">
                    {listing.description}
                  </p>
                )}
                <div className="flex gap-3 text-xs text-[var(--muted)]">
                  <span>{listing.industry}</span>
                  <span>{listing.region}</span>
                </div>
                {listing.anonymized_data && (
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div className="text-center p-2 rounded bg-[var(--background)]">
                      <p className="font-medium">
                        {(
                          listing.anonymized_data.scope1 as number
                        )?.toLocaleString() ?? "—"}
                      </p>
                      <p className="text-[var(--muted)]">Scope 1</p>
                    </div>
                    <div className="text-center p-2 rounded bg-[var(--background)]">
                      <p className="font-medium">
                        {(
                          listing.anonymized_data.scope2 as number
                        )?.toLocaleString() ?? "—"}
                      </p>
                      <p className="text-[var(--muted)]">Scope 2</p>
                    </div>
                    <div className="text-center p-2 rounded bg-[var(--background)]">
                      <p className="font-medium">
                        {(
                          listing.anonymized_data.scope3 as number
                        )?.toLocaleString() ?? "—"}
                      </p>
                      <p className="text-[var(--muted)]">Scope 3</p>
                    </div>
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--card-border)]">
                <span className="font-semibold">
                  {listing.price_credits === 0
                    ? "Free"
                    : `${listing.price_credits} credits`}
                </span>
                <button
                  className="btn-primary text-xs px-3 py-1.5"
                  onClick={() => setPurchaseTarget(listing.id)}
                >
                  Purchase
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!purchaseTarget}
        title="Confirm Purchase"
        message="Purchase this listing? Credits will be deducted."
        confirmLabel="Purchase"
        onConfirm={() => purchaseTarget && handlePurchase(purchaseTarget)}
        onCancel={() => setPurchaseTarget(null)}
      />
    </div>
  );
}
