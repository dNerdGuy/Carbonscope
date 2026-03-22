import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

const mockForgotPassword = vi.fn();
vi.mock("@/lib/api", () => ({
  forgotPassword: (...a: unknown[]) => mockForgotPassword(...a),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status = 400) {
      super(message);
      this.status = status;
    }
  },
}));

import { Route as _Route_ForgotPasswordPage } from "@/app/forgot-password";
const ForgotPasswordPage = _Route_ForgotPasswordPage.options.component!;

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the form", () => {
    render(<ForgotPasswordPage />);
    expect(screen.getByText("Forgot Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send Reset Link" }),
    ).toBeInTheDocument();
  });

  it("renders back to sign in link", () => {
    render(<ForgotPasswordPage />);
    const link = screen.getByRole("link", { name: /back to sign in/i });
    expect(link).toHaveAttribute("href", "/login");
  });

  it("disables button while submitting", async () => {
    mockForgotPassword.mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 200)),
    );
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));
    expect(screen.getByRole("button", { name: "Sending..." })).toBeDisabled();
  });

  it("shows success message after submission", async () => {
    mockForgotPassword.mockResolvedValueOnce(undefined);
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));
    await waitFor(() => {
      expect(mockForgotPassword).toHaveBeenCalledWith("user@test.com");
      expect(
        screen.getByText(/you will receive a password reset link/i),
      ).toBeInTheDocument();
    });
  });

  it("shows error on ApiError", async () => {
    const { ApiError } = await import("@/lib/api");
    mockForgotPassword.mockRejectedValueOnce(
      new ApiError(404, "Email not found"),
    );
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "noone@test.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));
    expect(await screen.findByText("Email not found")).toBeInTheDocument();
  });

  it("shows generic error on unexpected failure", async () => {
    mockForgotPassword.mockRejectedValueOnce(new Error("Network error"));
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));
    expect(
      await screen.findByText("An unexpected error occurred"),
    ).toBeInTheDocument();
  });
});
