import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

const mockListAuditLogs = vi.fn();

vi.mock("@/lib/api", () => ({
  listAuditLogs: (...a: unknown[]) => mockListAuditLogs(...a),
  ApiError: class extends Error {
    status: number;
    constructor(msg: string, status: number) {
      super(msg);
      this.status = status;
    }
  },
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "u@test.com" }, loading: false }),
}));

vi.mock("@/components/Skeleton", () => ({
  SkeletonRows: () => (
    <tr>
      <td>Loading...</td>
    </tr>
  ),
  TableSkeleton: () => <div>Loading...</div>,
}));

vi.mock("@/components/Breadcrumbs", () => ({
  default: () => <nav data-testid="breadcrumbs" />,
}));

vi.mock("@/components/StatusMessage", () => ({
  StatusMessage: ({ message }: { message: string }) => <div>{message}</div>,
}));

import { Route as _Route_AuditLogsPage } from "@/app/audit-logs";
const AuditLogsPage = _Route_AuditLogsPage.options.component!;

function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const LOGS = {
  items: [
    {
      id: "log1",
      action: "report.created",
      resource_type: "emission_report",
      resource_id: "r1",
      details: null,
      created_at: "2024-01-15T12:00:00Z",
    },
    {
      id: "log2",
      action: "data.uploaded",
      resource_type: "data_upload",
      resource_id: "u1",
      details: null,
      created_at: "2024-01-14T10:00:00Z",
    },
  ],
  total: 2,
};

describe("AuditLogsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAuditLogs.mockResolvedValue(LOGS);
  });

  it("renders heading", async () => {
    renderWithQueryClient(<AuditLogsPage />);
    expect(await screen.findByText("Audit Log")).toBeInTheDocument();
  });

  it("renders table headers", async () => {
    renderWithQueryClient(<AuditLogsPage />);
    expect(await screen.findByText("Timestamp")).toBeInTheDocument();
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Resource")).toBeInTheDocument();
    expect(screen.getByText("Details")).toBeInTheDocument();
  });

  it("displays audit log entries", async () => {
    renderWithQueryClient(<AuditLogsPage />);
    expect(
      (await screen.findAllByText("report.created")).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("data.uploaded").length).toBeGreaterThan(0);
  });

  it("shows empty state when no logs", async () => {
    mockListAuditLogs.mockResolvedValue({ items: [], total: 0 });
    renderWithQueryClient(<AuditLogsPage />);
    expect(
      (await screen.findAllByText(/No audit log entries found|No data found/))
        .length,
    ).toBeGreaterThan(0);
  });

  it("shows error on API failure", async () => {
    mockListAuditLogs.mockRejectedValue(new Error("Failed to load audit logs"));
    renderWithQueryClient(<AuditLogsPage />);
    expect(
      await screen.findByText(/Failed to load audit logs/),
    ).toBeInTheDocument();
  });

  it("has table role for accessibility", async () => {
    renderWithQueryClient(<AuditLogsPage />);
    await screen.findAllByText("report.created");
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
