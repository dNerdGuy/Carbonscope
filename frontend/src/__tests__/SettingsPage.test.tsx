import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { InputHTMLAttributes, ReactNode } from "react";

const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: mockReplace }),
  usePathname: () => "/settings",
  useSearchParams: () => new URLSearchParams(),
}));

const mockGetCompany = vi.fn();
const mockUpdateCompany = vi.fn();
const mockGetProfile = vi.fn();
const mockUpdateProfile = vi.fn();
const mockChangePassword = vi.fn();
const mockListWebhooks = vi.fn();
const mockCreateWebhook = vi.fn();
const mockDeleteWebhook = vi.fn();
const mockToggleWebhook = vi.fn();

vi.mock("@/lib/api", () => ({
  getCompany: (...a: unknown[]) => mockGetCompany(...a),
  updateCompany: (...a: unknown[]) => mockUpdateCompany(...a),
  getProfile: (...a: unknown[]) => mockGetProfile(...a),
  updateProfile: (...a: unknown[]) => mockUpdateProfile(...a),
  changePassword: (...a: unknown[]) => mockChangePassword(...a),
  listWebhooks: (...a: unknown[]) => mockListWebhooks(...a),
  createWebhook: (...a: unknown[]) => mockCreateWebhook(...a),
  deleteWebhook: (...a: unknown[]) => mockDeleteWebhook(...a),
  toggleWebhook: (...a: unknown[]) => mockToggleWebhook(...a),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: { email: "u@test.com" }, loading: false }),
}));

type FormFieldMockProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  children?: ReactNode;
};

type ConfirmDialogProps = {
  open: boolean;
  onConfirm: () => void;
  title: string;
};

vi.mock("@/components/FormField", () => ({
  FormField: ({ label, value, onChange, type, children, ...rest }: FormFieldMockProps) => (
    <label>
      {label}
      {children || (
        <input
          type={type || "text"}
          value={value}
          onChange={onChange}
          {...rest}
        />
      )}
    </label>
  ),
}));

vi.mock("@/components/Skeleton", () => ({
  PageSkeleton: () => <div>Loading...</div>,
}));

vi.mock("@/components/ConfirmDialog", () => ({
  default: ({ open, onConfirm, title }: ConfirmDialogProps) =>
    open ? (
      <div data-testid="confirm-dialog">
        <span>{title}</span>
        <button onClick={onConfirm}>Confirm</button>
      </div>
    ) : null,
}));

import SettingsPage from "@/app/settings/page";

const COMPANY = {
  id: "c1",
  name: "TestCo",
  industry: "technology",
  region: "US",
  employee_count: 50,
  revenue_usd: 1_000_000,
};

const PROFILE = {
  id: "u1",
  email: "u@test.com",
  full_name: "Test User",
  company_id: "c1",
  role: "admin",
};

function setupMocks() {
  mockGetCompany.mockResolvedValue(COMPANY);
  mockGetProfile.mockResolvedValue(PROFILE);
  mockListWebhooks.mockResolvedValue({ items: [] });
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it("renders heading", async () => {
    render(<SettingsPage />);
    expect(await screen.findByText("Settings")).toBeInTheDocument();
  });

  it("shows user profile fields", async () => {
    render(<SettingsPage />);
    expect(await screen.findByDisplayValue("Test User")).toBeInTheDocument();
    expect(screen.getByDisplayValue("u@test.com")).toBeInTheDocument();
  });

  it("shows company fields", async () => {
    render(<SettingsPage />);
    expect(await screen.findByDisplayValue("TestCo")).toBeInTheDocument();
  });

  it("shows webhook section heading", async () => {
    render(<SettingsPage />);
    expect(await screen.findByText("Webhooks")).toBeInTheDocument();
  });

  it("handles company save error", async () => {
    mockUpdateCompany.mockRejectedValue(new Error("Update failed"));
    render(<SettingsPage />);
    await screen.findByDisplayValue("TestCo");

    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() => {
      expect(mockUpdateCompany).toHaveBeenCalled();
    });
    expect(await screen.findByText("Update failed")).toBeInTheDocument();
  });

  it("saves profile on submit", async () => {
    mockUpdateProfile.mockResolvedValue({ ...PROFILE, full_name: "New Name" });
    render(<SettingsPage />);
    await screen.findByDisplayValue("Test User");

    const nameInput = screen.getByDisplayValue("Test User");
    fireEvent.change(nameInput, { target: { value: "New Name" } });

    fireEvent.click(screen.getByText("Update Profile"));

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalled();
    });
  });

  it("has password change section", async () => {
    render(<SettingsPage />);
    await screen.findByText("Settings");

    const heading = screen.getByRole("heading", { name: "Change Password" });
    expect(heading).toBeInTheDocument();
  });
});
