import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

const mockGetDashboard = vi.fn();
vi.mock("@/lib/api", () => ({
  getDashboard: () => mockGetDashboard(),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { email: "test@example.com" },
    loading: false,
  }),
}));

vi.mock("@/components/ScopeChart", () => ({
  default: () => <div data-testid="scope-chart" />,
}));

import { Route as _Route_DashboardPage } from "@/app/dashboard";
const DashboardPage = _Route_DashboardPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const MOCK_DATA = {
  company: { name: "Acme Corp", industry: "Technology" },
  latest_report: {
    total: 1234.5,
    scope1: 100,
    scope2: 200,
    scope3: 934.5,
    confidence: 0.87,
  },
  reports_count: 5,
  data_uploads_count: 12,
  year_over_year: [],
};

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockGetDashboard.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithQueryClient(<DashboardPage />);
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });

  it("renders dashboard data", async () => {
    mockGetDashboard.mockResolvedValue(MOCK_DATA);
    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText(/Acme Corp/)).toBeInTheDocument();
    expect(screen.getByText(/Technology/)).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument(); // reports count
    expect(screen.getByText("12")).toBeInTheDocument(); // uploads count
    expect(screen.getByText("87%")).toBeInTheDocument(); // confidence
  });

  it("renders scope chart when report exists", async () => {
    mockGetDashboard.mockResolvedValue(MOCK_DATA);
    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByTestId("scope-chart")).toBeInTheDocument();
  });

  it("renders error state", async () => {
    mockGetDashboard.mockRejectedValue(new Error("Network failed"));
    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText(/Network failed/)).toBeInTheDocument();
  });
});
