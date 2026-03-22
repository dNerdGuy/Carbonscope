import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockRegister = vi.fn();
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ register: mockRegister }),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/FormField", () => ({
  FormField: ({
    label,
    type,
    value,
    onChange,
    onBlur,
    error,
    children,
  }: {
    label: string;
    type?: string;
    value?: string;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
    error?: string;
    children?: React.ReactNode;
  }) => (
    <div>
      <label htmlFor={label}>{label}</label>
      {children ? (
        children
      ) : (
        <input
          id={label}
          type={type}
          value={value}
          onChange={onChange}
          onBlur={onBlur}
          aria-label={label}
        />
      )}
      {error && <span>{error}</span>}
    </div>
  ),
}));

vi.mock("@/lib/validation", () => ({
  validateRegisterField: vi.fn().mockReturnValue(null),
  validateRegisterForm: vi.fn().mockReturnValue({}),
}));

import { validateRegisterForm, validateRegisterField } from "@/lib/validation";
import { Route as _Route_RegisterPage } from "@/app/register";
const RegisterPage = _Route_RegisterPage.options.component!;

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the registration form", () => {
    render(<RegisterPage />);
    expect(screen.getByText(/create your account/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create account/i }),
    ).toBeInTheDocument();
  });

  it("renders link to sign in", () => {
    render(<RegisterPage />);
    const link = screen.getByRole("link", { name: /sign in/i });
    expect(link).toHaveAttribute("href", "/login");
  });

  it("calls register on valid form submit", async () => {
    mockRegister.mockResolvedValueOnce(undefined);
    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Test User" },
    });
    fireEvent.change(screen.getByLabelText(/company name/i), {
      target: { value: "ACME Corp" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalled();
    });
  });

  it("shows 409 conflict error for duplicate email", async () => {
    const err = Object.assign(new Error("Email already in use"), {
      status: 409,
    });
    mockRegister.mockRejectedValueOnce(err);
    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(
      await screen.findByText(/account with this email already exists/i),
    ).toBeInTheDocument();
  });

  it("shows 429 rate-limit error", async () => {
    const err = Object.assign(new Error("Too many requests"), { status: 429 });
    mockRegister.mockRejectedValueOnce(err);
    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/too many requests/i)).toBeInTheDocument();
  });

  it("shows generic error on unexpected failure", async () => {
    mockRegister.mockRejectedValueOnce(new Error("Network error"));
    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText("Network error")).toBeInTheDocument();
  });

  it("blocks submit when validation fails", async () => {
    vi.mocked(validateRegisterForm).mockReturnValueOnce({
      email: "Email is required",
    });
    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    const errors = await screen.findAllByText("Email is required");
    expect(errors.length).toBeGreaterThanOrEqual(1);
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("shows inline error on blur with invalid email", async () => {
    vi.mocked(validateRegisterField).mockReturnValueOnce(
      "Enter a valid email address",
    );
    render(<RegisterPage />);

    const emailInput = screen.getByLabelText("Email");
    fireEvent.change(emailInput, { target: { value: "bad" } });
    fireEvent.blur(emailInput);

    expect(
      await screen.findByText("Enter a valid email address"),
    ).toBeInTheDocument();
  });

  it("disables submit and shows 'Creating account...' while submitting", async () => {
    let resolveRegister!: () => void;
    mockRegister.mockReturnValueOnce(
      new Promise<void>((r) => {
        resolveRegister = r;
      }),
    );
    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText("Creating account...")).toBeInTheDocument();
    });
    expect(screen.getByText("Creating account...")).toBeDisabled();

    resolveRegister();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /create account/i }),
      ).toBeInTheDocument();
    });
  });

  it("shows 'Registration failed' for non-Error rejection", async () => {
    mockRegister.mockRejectedValueOnce("unknown");
    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText("Registration failed")).toBeInTheDocument();
  });

  it("shows err.message for non-409/429 status errors", async () => {
    const err = Object.assign(new Error("Internal error"), { status: 500 });
    mockRegister.mockRejectedValueOnce(err);
    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText("Internal error")).toBeInTheDocument();
  });

  it("renders industry select options", () => {
    render(<RegisterPage />);
    const options = screen.getAllByRole("option");
    const labels = options.map((o) => o.textContent);
    expect(labels).toContain("Energy");
    expect(labels).toContain("Manufacturing");
    expect(labels).toContain("Technology");
  });

  it("renders region select options", () => {
    render(<RegisterPage />);
    const options = screen.getAllByRole("option");
    const labels = options.map((o) => o.textContent);
    expect(labels).toContain("United States");
    expect(labels).toContain("European Union");
    expect(labels).toContain("Other");
  });
});
