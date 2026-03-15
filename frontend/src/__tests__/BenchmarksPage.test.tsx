import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  usePathname: () => "/benchmarks",
  useSearchParams: () => new URLSearchParams(),
}));

const mockGetIndustryBenchmarks = vi.fn();
const mockGetPeerComparison = vi.fn();

vi.mock("@/lib/api", () => ({
  getIndustryBenchmarks: (industry: string) =>
    mockGetIndustryBenchmarks(industry),
  getPeerComparison: () => mockGetPeerComparison(),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "test@example.com" }, loading: false }),
}));

import BenchmarksPage from "@/app/benchmarks/page";

describe("BenchmarksPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders heading", async () => {
    mockGetIndustryBenchmarks.mockResolvedValue({
      avg_total_tco2e: 5000,
      sample_size: 42,
    });
    mockGetPeerComparison.mockResolvedValue({
      percentile: "top_25",
      company_total: 3000,
      industry_avg: 5000,
    });
    render(<BenchmarksPage />);
    expect(await screen.findByText("Industry Benchmarks")).toBeInTheDocument();
  });

  it("renders benchmark metrics", async () => {
    mockGetIndustryBenchmarks.mockResolvedValue({
      avg_total_tco2e: 5000,
      sample_size: 42,
    });
    mockGetPeerComparison.mockResolvedValue({
      percentile: "top_25",
    });
    render(<BenchmarksPage />);
    expect(await screen.findByText("5,000")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("shows error on API failure", async () => {
    mockGetIndustryBenchmarks.mockRejectedValue(new Error("API down"));
    mockGetPeerComparison.mockRejectedValue(new Error("API down"));
    render(<BenchmarksPage />);
    expect(await screen.findByText(/API down/)).toBeInTheDocument();
  });

  it("has industry selector", async () => {
    mockGetIndustryBenchmarks.mockResolvedValue({ avg_total_tco2e: 100 });
    mockGetPeerComparison.mockResolvedValue({ percentile: "median" });
    render(<BenchmarksPage />);
    const selector = await screen.findByRole("combobox");
    expect(selector).toBeInTheDocument();
  });
});
