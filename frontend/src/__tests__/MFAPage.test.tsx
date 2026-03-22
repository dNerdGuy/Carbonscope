import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const mockGetMFAStatus = vi.fn();

vi.mock("@/lib/api", () => ({
  getMFAStatus: (...a: unknown[]) => mockGetMFAStatus(...a),
  setupMFA: vi.fn(),
  verifyMFA: vi.fn(),
  disableMFA: vi.fn(),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "test@example.com" }, loading: false }),
}));

// Track the queryFn provided to useQuery so each test can control its return
let _capturedQueryFn: (() => Promise<unknown>) | null = null;
let _queryResult: { data: unknown; isLoading: boolean; error: unknown } = {
  data: undefined,
  isLoading: true,
  error: null,
};

vi.mock("@tanstack/react-query", () => ({
  useQuery: (opts: { queryFn?: () => Promise<unknown>; enabled?: boolean }) => {
    if (opts.queryFn && opts.enabled !== false) {
      _capturedQueryFn = opts.queryFn;
    }
    return {
      ..._queryResult,
      isFetching: false,
      refetch: vi.fn(),
    };
  },
}));

import { Route as _Route_MFAPage } from "@/app/mfa";
const MFAPage = _Route_MFAPage.options.component!;

/**
 * Helper: render the component, resolve the useQuery mock data by calling
 * the captured queryFn, then re-render using the same container.
 */
async function renderAndResolve() {
  const result = render(<MFAPage />);
  if (_capturedQueryFn) {
    try {
      const data = await _capturedQueryFn();
      _queryResult = { data, isLoading: false, error: null };
    } catch (e) {
      _queryResult = { data: undefined, isLoading: false, error: e };
    }
  }
  result.rerender(<MFAPage />);
  return result;
}

describe("MFAPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _capturedQueryFn = null;
    _queryResult = { data: undefined, isLoading: true, error: null };
  });

  it("renders heading", async () => {
    mockGetMFAStatus.mockResolvedValue({ mfa_enabled: false });
    await renderAndResolve();
    expect(screen.getByText("Multi-Factor Authentication")).toBeInTheDocument();
  });

  it("shows MFA disabled status", async () => {
    mockGetMFAStatus.mockResolvedValue({ mfa_enabled: false });
    await renderAndResolve();
    expect(screen.getByText("MFA is disabled")).toBeInTheDocument();
    expect(screen.getByText("Enable MFA")).toBeInTheDocument();
  });

  it("shows MFA enabled status with disable section", async () => {
    mockGetMFAStatus.mockResolvedValue({ mfa_enabled: true });
    await renderAndResolve();
    expect(screen.getByText("MFA is enabled")).toBeInTheDocument();
    expect(screen.getByText("Disable MFA")).toBeInTheDocument();
  });

  it("handles API failure gracefully", async () => {
    mockGetMFAStatus.mockRejectedValue(new Error("Connection failed"));
    await renderAndResolve();
    // Page remains usable with heading visible (status defaults to null)
    expect(screen.getByText("Multi-Factor Authentication")).toBeInTheDocument();
  });
});
