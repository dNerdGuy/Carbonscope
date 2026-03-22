import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import Breadcrumbs from "@/components/Breadcrumbs";
import { PageSkeleton } from "@/components/Skeleton";
import { ErrorCard } from "@/components/ErrorCard";
import { DataTable, type Column } from "@/components/DataTable";
import {
  getMyMarketplaceSales,
  getMyMarketplaceRevenue,
  type DataPurchaseOut,
  type SellerRevenue,
  type PaginatedResponse,
} from "@/lib/api";

const PAGE_SIZE = 20;

export const Route = createFileRoute("/marketplace/seller")({ component: SellerDashboardPage });

function SellerDashboardPage() {
  const { user, loading } = useRequireAuth();
  const [offset, setOffset] = useState(0);

  const revenueQuery = useQuery<SellerRevenue>({
    queryKey: ["seller-revenue"],
    queryFn: () => getMyMarketplaceRevenue(),
    enabled: !!user,
  });

  const salesQuery = useQuery<PaginatedResponse<DataPurchaseOut>>({
    queryKey: ["seller-sales", offset],
    queryFn: () => getMyMarketplaceSales({ limit: PAGE_SIZE, offset }),
    enabled: !!user,
  });

  const error = revenueQuery.error || salesQuery.error;

  if (loading || (revenueQuery.isLoading && salesQuery.isLoading)) {
    return <PageSkeleton />;
  }

  const revenue = revenueQuery.data;
  const sales = salesQuery.data;

  const salesColumns: Column<DataPurchaseOut>[] = [
    {
      key: "listing_title",
      header: "Listing",
      render: (sale) => (
        <span className="font-medium">{sale.listing?.title ?? "—"}</span>
      ),
    },
    {
      key: "data_type",
      header: "Data Type",
      render: (sale) => (
        <span className="text-[var(--muted)]">
          {sale.listing?.data_type?.replace(/_/g, " ") ?? "—"}
        </span>
      ),
    },
    {
      key: "price_credits",
      header: "Price",
      render: (sale) => (
        <span className="font-medium">
          {sale.price_credits.toLocaleString()} cr
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Date",
      render: (sale) => (
        <span className="text-[var(--muted)]">
          {new Date(sale.created_at).toLocaleDateString()}
        </span>
      ),
    },
  ];

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">
      <Breadcrumbs
        items={[
          { label: "Marketplace", href: "/marketplace" },
          { label: "Seller Dashboard" },
        ]}
      />

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Seller Dashboard</h1>
        <Link to="/marketplace" className="btn-secondary text-sm">
          ← Back to Marketplace
        </Link>
      </div>

      {error && (
        <ErrorCard
          message={
            error instanceof Error
              ? error.message
              : "Failed to load seller data"
          }
          onRetry={() => {
            revenueQuery.refetch();
            salesQuery.refetch();
          }}
        />
      )}

      {/* Revenue summary cards */}
      {revenue && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card">
            <p className="text-[var(--muted)] text-sm">Total Revenue</p>
            <p className="text-2xl font-bold text-[var(--primary)]">
              {revenue.total_revenue_credits.toLocaleString()} credits
            </p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-sm">Total Sales</p>
            <p className="text-2xl font-bold">{revenue.total_sales}</p>
          </div>
          <div className="card">
            <p className="text-[var(--muted)] text-sm">Active Listings</p>
            <p className="text-2xl font-bold">{revenue.active_listings}</p>
          </div>
        </div>
      )}

      {/* Sales table */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Recent Sales</h2>
        <DataTable<DataPurchaseOut>
          columns={salesColumns}
          data={sales?.items ?? []}
          emptyMessage="No sales yet. List data on the marketplace to get started."
          caption="Recent sales"
          total={sales?.total}
          limit={PAGE_SIZE}
          offset={offset}
          onPageChange={setOffset}
        />
      </div>
    </div>
  );
}
