import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";

const mockListReviews = vi.fn();
const mockListReports = vi.fn();

vi.mock("@/lib/api", () => ({
  listReviews: () => mockListReviews(),
  listReports: () => mockListReports(),
  createReview: vi.fn(),
  reviewAction: vi.fn(),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "test@example.com" }, loading: false }),
}));

import { Route as _Route_ReviewsPage } from "@/app/reviews";
const ReviewsPage = _Route_ReviewsPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("ReviewsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListReviews.mockResolvedValue({ items: [] });
    mockListReports.mockResolvedValue({ items: [] });
  });

  it("renders heading", async () => {
    renderWithQueryClient(<ReviewsPage />);
    expect(await screen.findByText("Data Reviews")).toBeInTheDocument();
  });

  it("renders review list with status badges", async () => {
    mockListReviews.mockResolvedValue({
      items: [
        {
          id: "r1",
          report_id: "rpt12345678",
          status: "submitted",
          created_at: "2025-01-01T00:00:00Z",
          reviewed_at: null,
          reviewer_notes: null,
        },
      ],
    });
    renderWithQueryClient(<ReviewsPage />);
    expect(await screen.findByText("submitted")).toBeInTheDocument();
  });

  it("shows create form on button click", async () => {
    renderWithQueryClient(<ReviewsPage />);
    await userEvent.click(await screen.findByText("New Review"));
    expect(screen.getByText("Create Review for Report")).toBeInTheDocument();
  });

  it("shows error on API failure", async () => {
    mockListReviews.mockRejectedValue(new Error("Server error"));
    renderWithQueryClient(<ReviewsPage />);
    expect(await screen.findByText(/Server error/)).toBeInTheDocument();
  });
});
