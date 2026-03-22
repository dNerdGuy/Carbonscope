import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockLogin = vi.fn();
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ login: mockLogin }),
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
    ...rest
  }: {
    label: string;
    type: string;
    value: string;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  }) => (
    <label>
      {label}
      <input type={type} value={value} onChange={onChange} {...rest} />
    </label>
  ),
}));

import { Route as _Route_LoginPage } from "@/app/login";
const LoginPage = _Route_LoginPage.options.component!;

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders sign-in form", () => {
    render(<LoginPage />);
    expect(screen.getByText("CarbonScope")).toBeInTheDocument();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(screen.getByText("Forgot password?")).toBeInTheDocument();
  });

  it("calls login on submit", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("user@test.com", "secret123");
    });
  });

  it("shows 401 error message", async () => {
    const err = Object.assign(new Error("Unauthorized"), { status: 401 });
    mockLogin.mockRejectedValueOnce(err);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "bad@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByText("Sign In"));

    expect(
      await screen.findByText("Invalid email or password."),
    ).toBeInTheDocument();
  });

  it("shows rate limit error", async () => {
    const err = Object.assign(new Error("Rate limited"), { status: 429 });
    mockLogin.mockRejectedValueOnce(err);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pass" },
    });
    fireEvent.click(screen.getByText("Sign In"));

    expect(
      await screen.findByText("Too many requests. Please wait and try again."),
    ).toBeInTheDocument();
  });

  it("has links to register and forgot password", () => {
    render(<LoginPage />);
    const forgotLink = screen.getByText("Forgot password?");
    expect(forgotLink.closest("a")).toHaveAttribute("href", "/forgot-password");
    expect(screen.getByText("Register").closest("a")).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("disables submit and shows 'Signing in...' while submitting", async () => {
    let resolveLogin!: () => void;
    mockLogin.mockReturnValueOnce(
      new Promise<void>((r) => {
        resolveLogin = r;
      }),
    );
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "u@t.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw" },
    });
    fireEvent.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(screen.getByText("Signing in...")).toBeInTheDocument();
    });
    expect(screen.getByText("Signing in...")).toBeDisabled();

    resolveLogin();
    await waitFor(() => {
      expect(screen.getByText("Sign In")).toBeInTheDocument();
    });
  });

  it("shows error message for non-401/429 status errors", async () => {
    const err = Object.assign(new Error("Server Error"), { status: 500 });
    mockLogin.mockRejectedValueOnce(err);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "u@t.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw" },
    });
    fireEvent.click(screen.getByText("Sign In"));

    expect(await screen.findByText("Server Error")).toBeInTheDocument();
  });

  it("shows error message for errors without status property", async () => {
    mockLogin.mockRejectedValueOnce(new Error("Network down"));
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "u@t.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw" },
    });
    fireEvent.click(screen.getByText("Sign In"));

    expect(await screen.findByText("Network down")).toBeInTheDocument();
  });

  it("clears previous error on new submit attempt", async () => {
    const err = Object.assign(new Error("Unauthorized"), { status: 401 });
    mockLogin.mockRejectedValueOnce(err);
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "u@t.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw" },
    });
    fireEvent.click(screen.getByText("Sign In"));

    expect(
      await screen.findByText("Invalid email or password."),
    ).toBeInTheDocument();

    // Second submit should clear the error while in flight
    mockLogin.mockResolvedValueOnce(undefined);
    fireEvent.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(
        screen.queryByText("Invalid email or password."),
      ).not.toBeInTheDocument();
    });
  });
});
