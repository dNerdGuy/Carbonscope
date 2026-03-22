import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

const mockListReports = vi.fn();
vi.mock("@/lib/api", () => ({
  listReports: (...args: unknown[]) => mockListReports(...args),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", company_id: "co1" },
    loading: false,
  }),
}));

vi.mock("@/components/Breadcrumbs", () => ({
  default: () => <nav data-testid="breadcrumbs" />,
}));

import { Route as _Route_RecommendationsIndexPage } from "@/app/recommendations";
const RecommendationsIndexPage = _Route_RecommendationsIndexPage.options.component!;

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("RecommendationsIndexPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows empty state when no reports", async () => {
    mockListReports.mockResolvedValue({ items: [], total: 0 });
    renderWithQuery(<RecommendationsIndexPage />);

    expect(await screen.findByText("No reports yet")).toBeInTheDocument();
    expect(screen.getByText("Upload Data")).toBeInTheDocument();
  });

  it("renders report cards", async () => {
    mockListReports.mockResolvedValue({
      items: [
        {
          id: "r1",
          year: 2024,
          total: 5000,
          scope1: 1000,
          scope2: 2000,
          scope3: 2000,
          confidence: 0.92,
        },
      ],
      total: 1,
    });
    renderWithQuery(<RecommendationsIndexPage />);

    expect(await screen.findByText("2024 Emission Report")).toBeInTheDocument();
    expect(screen.getByText(/5,000 tCO₂e/)).toBeInTheDocument();
    expect(screen.getByText(/92% confidence/)).toBeInTheDocument();
  });

  it("links to individual recommendation page", async () => {
    mockListReports.mockResolvedValue({
      items: [
        {
          id: "abc123",
          year: 2023,
          total: 100,
          scope1: 30,
          scope2: 30,
          scope3: 40,
          confidence: 0.8,
        },
      ],
      total: 1,
    });
    renderWithQuery(<RecommendationsIndexPage />);

    const card = await screen.findByText("2023 Emission Report");
    expect(card.closest("a")).toHaveAttribute(
      "href",
      "/recommendations/abc123",
    );
  });

  it("shows error message on API failure", async () => {
    mockListReports.mockRejectedValue(new Error("Server error"));
    renderWithQuery(<RecommendationsIndexPage />);

    expect(await screen.findByText(/Server error/)).toBeInTheDocument();
  });
});
