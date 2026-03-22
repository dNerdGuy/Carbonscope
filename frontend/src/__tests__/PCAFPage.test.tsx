import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";

const mockListPortfolios = vi.fn();
const mockCreatePortfolio = vi.fn();
const mockGetPortfolioSummary = vi.fn();
const mockListPortfolioAssets = vi.fn();

vi.mock("@/lib/api", () => ({
  listPortfolios: () => mockListPortfolios(),
  createPortfolio: (data: unknown) => mockCreatePortfolio(data),
  getPortfolioSummary: (id: string) => mockGetPortfolioSummary(id),
  listPortfolioAssets: (id: string) => mockListPortfolioAssets(id),
  addPortfolioAsset: vi.fn(),
  deletePortfolioAsset: vi.fn(),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "test@example.com" }, loading: false }),
}));

import { Route as _Route_PCAFPage } from "@/app/pcaf";
const PCAFPage = _Route_PCAFPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PCAFPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListPortfolios.mockResolvedValue({ items: [] });
  });

  it("renders heading", async () => {
    renderWithQueryClient(<PCAFPage />);
    expect(
      await screen.findByText("PCAF Financed Emissions"),
    ).toBeInTheDocument();
  });

  it("renders portfolio list", async () => {
    mockListPortfolios.mockResolvedValue({
      items: [{ id: "p1", name: "Portfolio A", year: 2025, company_id: "c1" }],
    });
    renderWithQueryClient(<PCAFPage />);
    expect(await screen.findByText("Portfolio A")).toBeInTheDocument();
  });

  it("shows create form on button click", async () => {
    renderWithQueryClient(<PCAFPage />);
    await userEvent.click(await screen.findByText("New Portfolio"));
    expect(screen.getByText("Create Portfolio")).toBeInTheDocument();
  });

  it("shows error on API failure", async () => {
    mockListPortfolios.mockRejectedValue(new Error("Network error"));
    renderWithQueryClient(<PCAFPage />);
    expect(await screen.findByText(/Network error/)).toBeInTheDocument();
  });
});
