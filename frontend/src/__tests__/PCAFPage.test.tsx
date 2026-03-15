import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  usePathname: () => "/pcaf",
  useSearchParams: () => new URLSearchParams(),
}));

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

import PCAFPage from "@/app/pcaf/page";

describe("PCAFPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListPortfolios.mockResolvedValue({ items: [] });
  });

  it("renders heading", async () => {
    render(<PCAFPage />);
    expect(
      await screen.findByText("PCAF Financed Emissions"),
    ).toBeInTheDocument();
  });

  it("renders portfolio list", async () => {
    mockListPortfolios.mockResolvedValue({
      items: [{ id: "p1", name: "Portfolio A", year: 2025, company_id: "c1" }],
    });
    render(<PCAFPage />);
    expect(await screen.findByText("Portfolio A")).toBeInTheDocument();
  });

  it("shows create form on button click", async () => {
    render(<PCAFPage />);
    await userEvent.click(screen.getByText("New Portfolio"));
    expect(screen.getByText("Create Portfolio")).toBeInTheDocument();
  });

  it("shows error on API failure", async () => {
    mockListPortfolios.mockRejectedValue(new Error("Network error"));
    render(<PCAFPage />);
    expect(await screen.findByText(/Network error/)).toBeInTheDocument();
  });
});
