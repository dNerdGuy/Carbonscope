import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockUploadData = vi.fn();
const mockCreateEstimate = vi.fn();

vi.mock("@/lib/api", () => ({
  uploadData: (...a: unknown[]) => mockUploadData(...a),
  createEstimate: (...a: unknown[]) => mockCreateEstimate(...a),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "u@test.com" }, loading: false }),
}));

vi.mock("@/components/Skeleton", () => ({
  PageSkeleton: () => <div>Loading...</div>,
}));

import { Route as _Route_UploadPage } from "@/app/upload";
const UploadPage = _Route_UploadPage.options.component!;

describe("UploadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders heading", () => {
    render(<UploadPage />);
    expect(screen.getByText("Upload Operational Data")).toBeInTheDocument();
  });

  it("has year selector", () => {
    render(<UploadPage />);
    const selects = screen.getAllByRole("combobox");
    expect(selects.length).toBeGreaterThan(0);
  });

  it("submits form and shows success", async () => {
    mockUploadData.mockResolvedValue({ id: "upload-1" });
    mockCreateEstimate.mockResolvedValue({
      total: 1234,
      confidence: 0.85,
    });
    render(<UploadPage />);
    const submitBtn = screen.getByText("Upload & Estimate");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockUploadData).toHaveBeenCalled();
    });
    expect(await screen.findByText(/1,234/)).toBeInTheDocument();
  });

  it("shows error on failure", async () => {
    mockUploadData.mockRejectedValue(new Error("Upload failed"));
    render(<UploadPage />);
    const submitBtn = screen.getByText("Upload & Estimate");
    fireEvent.click(submitBtn);
    expect(await screen.findByText("Upload failed")).toBeInTheDocument();
  });

  it("has scope section labels", () => {
    render(<UploadPage />);
    expect(screen.getByText("Scope 1 — Direct Emissions")).toBeInTheDocument();
    expect(screen.getByText("Scope 2 — Purchased Energy")).toBeInTheDocument();
  });
});
