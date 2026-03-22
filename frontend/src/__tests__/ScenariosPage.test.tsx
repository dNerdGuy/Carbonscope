import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

const mockListScenarios = vi.fn();
const mockListReports = vi.fn();
const mockCreateScenario = vi.fn();
const mockComputeScenario = vi.fn();
const mockDeleteScenario = vi.fn();

vi.mock("@/lib/api", () => ({
  listReports: (...a: unknown[]) => mockListReports(...a),
  listScenarios: (...a: unknown[]) => mockListScenarios(...a),
  createScenario: (...a: unknown[]) => mockCreateScenario(...a),
  computeScenario: (...a: unknown[]) => mockComputeScenario(...a),
  deleteScenario: (...a: unknown[]) => mockDeleteScenario(...a),
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

import { Route as _Route_ScenariosPage } from "@/app/scenarios";
const ScenariosPage = _Route_ScenariosPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const SCENARIO = {
  id: "s1",
  name: "Green Plan",
  description: "Test",
  base_report_id: "r1",
  parameters: { energy_switch: { renewable_pct: 50 } },
  status: "draft",
  result: null,
  created_at: "2024-01-01T00:00:00Z",
};

const REPORT = { id: "r1", year: 2024, total: 5000 };

describe("ScenariosPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListScenarios.mockResolvedValue({ items: [SCENARIO], total: 1 });
    mockListReports.mockResolvedValue({ items: [REPORT], total: 1 });
  });

  it("renders heading and scenarios list", async () => {
    renderWithQueryClient(<ScenariosPage />);
    expect(await screen.findByText("What-If Scenarios")).toBeInTheDocument();
    expect(await screen.findByText("Green Plan")).toBeInTheDocument();
  });

  it("shows create form when button clicked", async () => {
    renderWithQueryClient(<ScenariosPage />);
    const btn = await screen.findByText("New Scenario");
    fireEvent.click(btn);
    expect(screen.getByText("Create Scenario")).toBeInTheDocument();
  });

  it("creates a scenario through the form", async () => {
    mockCreateScenario.mockResolvedValue({ id: "s2" });
    mockComputeScenario.mockResolvedValue({});
    renderWithQueryClient(<ScenariosPage />);

    fireEvent.click(await screen.findByText("New Scenario"));

    const nameInput = screen.getByPlaceholderText(
      "e.g., 100% Renewable by 2030",
    );
    fireEvent.change(nameInput, { target: { value: "Test Scenario" } });

    // Toggle an adjustment
    fireEvent.click(screen.getByText("Renewable Energy Switch"));

    fireEvent.click(screen.getByText("Create & Compute"));

    await waitFor(() => {
      expect(mockCreateScenario).toHaveBeenCalledTimes(1);
    });
    expect(mockComputeScenario).toHaveBeenCalledWith("s2");
  });

  it("shows error on fetch failure", async () => {
    mockListScenarios.mockRejectedValue(new Error("fail"));
    mockListReports.mockRejectedValue(new Error("fail"));
    renderWithQueryClient(<ScenariosPage />);
    expect(await screen.findByText("Failed to load data")).toBeInTheDocument();
  });

  it("has a status filter dropdown", async () => {
    renderWithQueryClient(<ScenariosPage />);
    const select = await screen.findByLabelText("Filter by status");
    expect(select).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "computed" } });
    await waitFor(() => {
      expect(mockListScenarios).toHaveBeenCalledWith(
        expect.objectContaining({ status: "computed" }),
      );
    });
  });
});
