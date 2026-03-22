import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockListReports = vi.fn();
const mockGenerateComplianceReport = vi.fn();

vi.mock("@/lib/api", () => ({
  listReports: (...a: unknown[]) => mockListReports(...a),
  generateComplianceReport: (...a: unknown[]) =>
    mockGenerateComplianceReport(...a),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { email: "u@test.com", company_id: "c1" },
    loading: false,
  }),
}));

vi.mock("@/components/Skeleton", () => ({
  PageSkeleton: () => <div>Loading...</div>,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: {
      items: [
        {
          id: "r1",
          year: 2024,
          total: 5000,
          company_id: "c1",
          scope1: 1000,
          scope2: 2000,
          scope3: 2000,
          breakdown: null,
          confidence: 0.85,
          sources: [],
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
    refetch: vi.fn(),
  }),
}));

import { Route as _Route_CompliancePage } from "@/app/compliance";
const CompliancePage = _Route_CompliancePage.options.component!;

describe("CompliancePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListReports.mockResolvedValue({
      items: [{ id: "r1", year: 2024, total: 5000 }],
      total: 1,
    });
  });

  it("renders heading", async () => {
    render(<CompliancePage />);
    expect(await screen.findByText("Compliance Reports")).toBeInTheDocument();
  });

  it("renders all framework buttons", async () => {
    render(<CompliancePage />);
    expect(await screen.findByText("GHG Protocol")).toBeInTheDocument();
    expect(screen.getByText("CDP Climate Change")).toBeInTheDocument();
    expect(screen.getByText("TCFD")).toBeInTheDocument();
    expect(screen.getByText("SBTi Pathway")).toBeInTheDocument();
  });

  it("has generate button", async () => {
    render(<CompliancePage />);
    expect(await screen.findByText("Generate Report")).toBeInTheDocument();
  });

  it("generates compliance report", async () => {
    mockGenerateComplianceReport.mockResolvedValue({
      framework: "ghg_protocol",
      data: {},
    });
    render(<CompliancePage />);
    await screen.findByText("Generate Report");
    fireEvent.click(screen.getByText("Generate Report"));

    await waitFor(() => {
      expect(mockGenerateComplianceReport).toHaveBeenCalled();
    });
  });

  it("shows error on generation failure", async () => {
    mockGenerateComplianceReport.mockRejectedValue(
      new Error("Generation failed"),
    );
    render(<CompliancePage />);
    await screen.findByText("Generate Report");
    fireEvent.click(screen.getByText("Generate Report"));
    expect(await screen.findByText("Generation failed")).toBeInTheDocument();
  });
});
