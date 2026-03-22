import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/Skeleton", () => ({
  CardSkeleton: () => <div>Loading...</div>,
}));

const mockListReports = vi.fn();
const mockExportReports = vi.fn();

vi.mock("@/lib/api", () => ({
  listReports: (...a: unknown[]) => mockListReports(...a),
  exportReports: (...a: unknown[]) => mockExportReports(...a),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "user@test.com" }, loading: false }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => {
    return {
      data: {
        items: [
          {
            id: "r1",
            company_id: "c1",
            year: 2024,
            scope1: 1000,
            scope2: 2000,
            scope3: 3000,
            total: 6000,
            breakdown: null,
            confidence: 0.85,
            sources: ["EPA"],
            assumptions: null,
            methodology_version: "ghg_protocol_v2025",
            miner_scores: null,
            created_at: "2024-01-01T00:00:00Z",
          },
        ],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      error: null,
    };
  },
}));

import { Route as _Route_ReportsPage } from "@/app/reports";
const ReportsPage = _Route_ReportsPage.options.component!;

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders reports heading", async () => {
    render(<ReportsPage />);
    expect(await screen.findByText(/emission reports/i)).toBeInTheDocument();
  });

  it("shows sort controls", async () => {
    render(<ReportsPage />);
    await screen.findByText(/emission reports/i);
    expect(screen.getByLabelText(/sort by/i)).toBeInTheDocument();
  });

  it("shows export buttons", async () => {
    render(<ReportsPage />);
    await screen.findByText(/emission reports/i);
    expect(
      screen.getByRole("button", { name: /export csv/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /export json/i }),
    ).toBeInTheDocument();
  });

  it("calls exportReports on export CSV click", async () => {
    mockExportReports.mockResolvedValueOnce(
      new Blob(["year,total\n2024,6000\n"]),
    );
    render(<ReportsPage />);
    await screen.findByText(/emission reports/i);
    fireEvent.click(screen.getByRole("button", { name: /export csv/i }));
    await waitFor(() => {
      expect(mockExportReports).toHaveBeenCalledWith("csv", undefined);
    });
  });

  it("renders year filter input", async () => {
    render(<ReportsPage />);
    await screen.findByText(/emission reports/i);
    expect(screen.getByPlaceholderText(/year/i)).toBeInTheDocument();
  });
});
