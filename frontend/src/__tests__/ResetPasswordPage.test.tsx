import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockSearchParams = new URLSearchParams("token=abc123");

const mockResetPassword = vi.fn();

vi.mock("@/lib/api", () => ({
  resetPassword: (...a: unknown[]) => mockResetPassword(...a),
  ApiError: class ApiError extends Error {
    constructor(message: string) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

import { Route as _Route_ResetPasswordPage } from "@/app/reset-password";
const ResetPasswordPage = _Route_ResetPasswordPage.options.component!;

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Ensure token is present by default
    if (!mockSearchParams.has("token")) {
      mockSearchParams.set("token", "abc123");
    }
  });

  it("renders heading and form fields", () => {
    render(<ResetPasswordPage />);
    expect(
      screen.getByRole("heading", { name: /reset password/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm Password")).toBeInTheDocument();
  });

  it("shows error when passwords do not match", async () => {
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Different1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    expect(
      await screen.findByText("Passwords do not match"),
    ).toBeInTheDocument();
  });

  it("shows error for weak password", async () => {
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "short" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    expect(
      await screen.findByText("Password must be at least 8 characters"),
    ).toBeInTheDocument();
  });

  it("submits valid passwords and shows success", async () => {
    mockResetPassword.mockResolvedValue({});
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalledWith("abc123", "StrongPass1!");
    });
    expect(
      await screen.findByText(/password has been reset successfully/i),
    ).toBeInTheDocument();
  });

  it("shows API error on failure", async () => {
    const { ApiError } = await import("@/lib/api");
    mockResetPassword.mockRejectedValue(new ApiError(400, "Token expired"));
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "StrongPass1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    expect(await screen.findByText("Token expired")).toBeInTheDocument();
  });
});
