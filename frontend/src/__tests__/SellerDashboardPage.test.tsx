import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

const mockGetRevenue = vi.fn();
const mockGetSales = vi.fn();
vi.mock("@/lib/api", () => ({
  getMyMarketplaceRevenue: () => mockGetRevenue(),
  getMyMarketplaceSales: (...args: unknown[]) => mockGetSales(...args),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { email: "seller@test.com" },
    loading: false,
  }),
}));

vi.mock("@/components/Breadcrumbs", () => ({
  default: () => <nav data-testid="breadcrumbs" />,
}));

vi.mock("@/components/Skeleton", () => ({
  PageSkeleton: () => <div>Loading...</div>,
}));

vi.mock("@/components/ErrorCard", () => ({
  ErrorCard: ({ message }: { message: string }) => (
    <div role="alert">{message}</div>
  ),
}));

vi.mock("@/components/DataTable", () => ({
  DataTable: ({
    data,
    emptyMessage,
  }: {
    data: unknown[];
    emptyMessage?: string;
    columns: unknown[];
  }) =>
    data.length === 0 ? (
      <div>{emptyMessage ?? "No data found"}</div>
    ) : (
      <table>
        <tbody>
          {data.map((row: unknown, i: number) => {
            const r = row as Record<string, unknown>;
            const listing = r.listing as Record<string, string> | undefined;
            return (
              <tr key={i}>
                <td>{listing?.title ?? ""}</td>
                <td>{listing?.data_type ?? ""}</td>
                <td>{String(r.price_credits ?? "")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    ),
}));

import { Route as _Route_SellerDashboardPage } from "@/app/marketplace.seller";
const SellerDashboardPage = _Route_SellerDashboardPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const MOCK_REVENUE = {
  total_revenue_credits: 5000,
  total_sales: 12,
  active_listings: 3,
};

const MOCK_SALES = {
  items: [
    {
      id: "p1",
      listing_id: "l1",
      buyer_company_id: "c1",
      price_credits: 100,
      purchased_at: "2024-01-15T10:00:00Z",
      listing: { title: "EU Carbon Data 2024", data_type: "emissions" },
    },
  ],
  total: 1,
};

describe("SellerDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders revenue summary cards", async () => {
    mockGetRevenue.mockResolvedValue(MOCK_REVENUE);
    mockGetSales.mockResolvedValue(MOCK_SALES);
    renderWithQueryClient(<SellerDashboardPage />);

    expect(await screen.findByText(/5,000 credits/)).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders sales table", async () => {
    mockGetRevenue.mockResolvedValue(MOCK_REVENUE);
    mockGetSales.mockResolvedValue(MOCK_SALES);
    renderWithQueryClient(<SellerDashboardPage />);

    expect(
      (await screen.findAllByText("EU Carbon Data 2024")).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("emissions").length).toBeGreaterThan(0);
  });

  it("shows empty sales message when no sales", async () => {
    mockGetRevenue.mockResolvedValue({
      total_revenue_credits: 0,
      total_sales: 0,
      active_listings: 0,
    });
    mockGetSales.mockResolvedValue({ items: [], total: 0 });
    renderWithQueryClient(<SellerDashboardPage />);

    expect((await screen.findAllByText(/no sales/i)).length).toBeGreaterThan(0);
  });

  it("shows error on API failure", async () => {
    mockGetRevenue.mockRejectedValue(new Error("Forbidden"));
    mockGetSales.mockResolvedValue({ items: [], total: 0 });
    renderWithQueryClient(<SellerDashboardPage />);

    expect(await screen.findByText(/Forbidden/)).toBeInTheDocument();
  });
});
