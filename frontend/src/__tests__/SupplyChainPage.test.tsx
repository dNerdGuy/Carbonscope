import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

const mockListSuppliers = vi.fn();
const mockAddSupplier = vi.fn();
const mockGetScope3 = vi.fn();
const mockUpdateLink = vi.fn();
const mockDeleteLink = vi.fn();

vi.mock("@/lib/api", () => ({
  listSuppliers: (...a: unknown[]) => mockListSuppliers(...a),
  addSupplier: (...a: unknown[]) => mockAddSupplier(...a),
  getScope3FromSuppliers: (...a: unknown[]) => mockGetScope3(...a),
  updateSupplyChainLink: (...a: unknown[]) => mockUpdateLink(...a),
  deleteSupplyChainLink: (...a: unknown[]) => mockDeleteLink(...a),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { email: "u@test.com", company_id: "c1" },
    loading: false,
  }),
}));

vi.mock("@/components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock("@/components/Skeleton", () => ({
  PageSkeleton: () => <div>Loading...</div>,
}));

type ConfirmDialogProps = {
  open: boolean;
  onConfirm: () => void;
  title: string;
};

vi.mock("@/components/ConfirmDialog", () => ({
  default: ({ open, onConfirm, title }: ConfirmDialogProps) =>
    open ? (
      <div data-testid="confirm-dialog">
        <span>{title}</span>
        <button onClick={onConfirm}>Confirm</button>
      </div>
    ) : null,
}));

import { Route as _Route_SupplyChainPage } from "@/app/supply-chain";
const SupplyChainPage = _Route_SupplyChainPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const SUPPLIER = {
  link_id: "l1",
  company_id: "s1",
  company_name: "SupplierCo",
  industry: "manufacturing",
  region: "EU",
  spend_usd: 50000,
  category: "general",
  status: "active",
  emissions: {
    scope1: 100,
    scope2: 200,
    total: 300,
    confidence: 0.8,
    year: 2024,
  },
  created_at: "2024-01-01T00:00:00Z",
};

const SCOPE3 = {
  scope3_cat1_from_suppliers: 1200,
  supplier_count: 3,
  verified_count: 1,
  coverage_pct: 45,
};

describe("SupplyChainPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListSuppliers.mockResolvedValue({ items: [SUPPLIER], total: 1 });
    mockGetScope3.mockResolvedValue(SCOPE3);
  });

  it("renders heading and supplier list", async () => {
    renderWithQueryClient(<SupplyChainPage />);
    expect(await screen.findByText("Supply Chain Network")).toBeInTheDocument();
    expect(await screen.findByText("SupplierCo")).toBeInTheDocument();
  });

  it("shows scope3 summary cards", async () => {
    renderWithQueryClient(<SupplyChainPage />);
    expect(await screen.findByText(/1,200 tCO₂e/)).toBeInTheDocument();
  });

  it("adds a supplier", async () => {
    mockAddSupplier.mockResolvedValue({});
    renderWithQueryClient(<SupplyChainPage />);

    await screen.findByText("Supply Chain Network");

    // Label is not linked via htmlFor, find parent div and get input
    const label = screen.getByText("Supplier Company ID");
    const idInput = label.parentElement!.querySelector("input")!;
    fireEvent.change(idInput, {
      target: { value: "550e8400-e29b-41d4-a716-446655440000" },
    });

    const addBtn = screen.getByRole("button", { name: /add supplier/i });
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(mockAddSupplier).toHaveBeenCalledWith(
        expect.objectContaining({
          supplier_company_id: "550e8400-e29b-41d4-a716-446655440000",
        }),
      );
    });
  });

  it("shows error on fetch failure", async () => {
    mockListSuppliers.mockRejectedValue(new Error("fail"));
    mockGetScope3.mockRejectedValue(new Error("fail"));
    renderWithQueryClient(<SupplyChainPage />);
    expect(await screen.findByText("fail")).toBeInTheDocument();
  });
});
