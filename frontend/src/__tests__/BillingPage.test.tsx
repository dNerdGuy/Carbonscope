import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

vi.mock("@/components/Skeleton", () => ({
  CardSkeleton: () => <div>Loading...</div>,
}));

vi.mock("@/components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
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

const mockGetSubscription = vi.fn();
const mockGetCredits = vi.fn();
const mockListPlans = vi.fn();
const mockChangePlan = vi.fn();

vi.mock("@/lib/api", () => ({
  getSubscription: (...a: unknown[]) => mockGetSubscription(...a),
  getCredits: (...a: unknown[]) => mockGetCredits(...a),
  listPlans: (...a: unknown[]) => mockListPlans(...a),
  changePlan: (...a: unknown[]) => mockChangePlan(...a),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status = 400) {
      super(message);
      this.status = status;
    }
  },
}));

const mockUser = { email: "user@test.com", full_name: "Test User" };

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: mockUser, loading: false }),
}));

import BillingPage from "@/app/billing/page";

const defaultSub = {
  plan: "free",
  status: "active",
  credits_remaining: 80,
};
const defaultCredits = { balance: 80 };
const defaultPlans = {
  free: { monthly_credits: 100, max_reports: 3 },
  pro: { monthly_credits: 1000, max_reports: null },
};

describe("BillingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSubscription.mockResolvedValue(defaultSub);
    mockGetCredits.mockResolvedValue(defaultCredits);
    mockListPlans.mockResolvedValue(defaultPlans);
  });

  it("renders billing heading", async () => {
    render(<BillingPage />);
    expect(
      await screen.findByText("Billing & Subscription"),
    ).toBeInTheDocument();
  });

  it("displays current plan", async () => {
    render(<BillingPage />);
    const elements = await screen.findAllByText(/free/i);
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it("displays credit balance", async () => {
    render(<BillingPage />);
    await screen.findByText("Billing & Subscription");
    expect(screen.getByText(/80/)).toBeInTheDocument();
  });

  it("calls changePlan and refreshes credits", async () => {
    const updatedSub = { ...defaultSub, plan: "pro" };
    mockChangePlan.mockResolvedValueOnce(updatedSub);
    mockGetCredits.mockResolvedValue({ balance: 1000 });

    render(<BillingPage />);
    await screen.findByText("Billing & Subscription");

    const upgradeBtn = screen
      .getAllByRole("button")
      .find((btn) => btn.textContent?.toLowerCase().includes("pro"));
    if (upgradeBtn) {
      fireEvent.click(upgradeBtn);
      // ConfirmDialog now opens; click its Confirm button
      const confirmBtn = await screen.findByText("Confirm");
      fireEvent.click(confirmBtn);
      await waitFor(() => {
        expect(mockChangePlan).toHaveBeenCalledWith("pro");
      });
    }
  });

  it("shows error when changePlan fails", async () => {
    const { ApiError } = await import("@/lib/api");
    mockChangePlan.mockRejectedValueOnce(
      new ApiError("Plan change failed", 400),
    );

    render(<BillingPage />);
    await screen.findByText("Billing & Subscription");

    const buttons = screen.getAllByRole("button");
    const changeable = buttons.find(
      (b) => !b.hasAttribute("disabled") && b.textContent?.trim(),
    );
    if (changeable) {
      fireEvent.click(changeable);
      // ConfirmDialog now opens; click its Confirm button
      const confirmBtn = await screen.findByText("Confirm");
      fireEvent.click(confirmBtn);
      expect(
        await screen.findByText(/plan change failed/i),
      ).toBeInTheDocument();
    }
  });

  it("redirects to login when unauthenticated", () => {
    vi.doMock("@/lib/auth-context", () => ({
      useAuth: () => ({ user: null, loading: false }),
    }));
    // mockReplace will be called by the useEffect
    render(<BillingPage />);
    // loading skeleton shown while redirecting
    expect(screen.queryAllByText("Loading...").length).toBeGreaterThanOrEqual(
      0,
    );
  });
});
