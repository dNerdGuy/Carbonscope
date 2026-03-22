import { createFileRoute, Link, useLocation } from "@tanstack/react-router";
import { Suspense, useState } from "react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { resetPassword, ApiError } from "@/lib/api";

export const Route = createFileRoute("/reset-password")({
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          <p>Loading...</p>
        </div>
      }
    >
      <ResetPasswordPageInner />
    </Suspense>
  );
}

function ResetPasswordPageInner() {
  useDocumentTitle("Reset Password");
  const token = new URLSearchParams(useLocation().search).get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const missingToken = !token;

  function validatePassword(pw: string): string | null {
    if (pw.length < 8) return "Password must be at least 8 characters";
    if (!/[A-Z]/.test(pw)) return "Must contain an uppercase letter";
    if (!/[a-z]/.test(pw)) return "Must contain a lowercase letter";
    if (!/\d/.test(pw)) return "Must contain a digit";
    if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(pw))
      return "Must contain a special character";
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    const pwError = validatePassword(password);
    if (pwError) {
      setError(pwError);
      return;
    }
    if (!token) {
      setError("Missing reset token. Please use the link from your email.");
      return;
    }
    setLoading(true);
    try {
      await resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen px-4">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold mb-2">Reset Password</h1>
        {success ? (
          <div>
            <p className="text-[var(--muted)] mb-4">
              Your password has been reset successfully.
            </p>
            <Link to="/login" className="btn-primary inline-block">
              Sign In
            </Link>
          </div>
        ) : (
          <>
            <p className="text-[var(--muted)] mb-6">Enter your new password.</p>
            {missingToken && (
              <div
                className="px-4 py-2 rounded-lg mb-4 text-sm"
                style={{
                  background:
                    "color-mix(in srgb, var(--warning) 10%, transparent)",
                  border: "1px solid var(--warning)",
                  color: "var(--warning)",
                }}
              >
                No reset token found. Please use the link from your password
                reset email.
              </div>
            )}
            {error && (
              <div className="bg-[var(--danger)]/10 border border-[var(--danger)] text-[var(--danger)] px-4 py-2 rounded-lg mb-4 text-sm">
                {error}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="password" className="label">
                  New Password
                </label>
                <input
                  id="password"
                  type="password"
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  autoFocus
                />
              </div>
              <div>
                <label htmlFor="confirm" className="label">
                  Confirm Password
                </label>
                <input
                  id="confirm"
                  type="password"
                  className="input"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
              <button
                type="submit"
                className="btn-primary w-full"
                disabled={loading}
              >
                {loading ? "Resetting..." : "Reset Password"}
              </button>
            </form>
            <p className="text-sm text-[var(--muted)] mt-4">
              <Link
                to="/login"
                className="text-[var(--primary)] hover:underline"
              >
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
