"use client";

import { useState } from "react";
import Link from "next/link";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { forgotPassword, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  useDocumentTitle("Forgot Password");
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await forgotPassword(email);
      setSubmitted(true);
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
        <h1 className="text-2xl font-bold mb-2">Forgot Password</h1>
        {submitted ? (
          <div>
            <p className="text-[var(--muted)] mb-4">
              If an account exists with that email, you will receive a password
              reset link shortly.
            </p>
            <Link
              href="/login"
              className="text-[var(--primary)] hover:underline"
            >
              Back to sign in
            </Link>
          </div>
        ) : (
          <>
            <p className="text-[var(--muted)] mb-6">
              Enter your email and we&apos;ll send you a reset link.
            </p>
            {error && (
              <div className="bg-[var(--danger)]/10 border border-[var(--danger)] text-[var(--danger)] px-4 py-2 rounded-lg mb-4 text-sm">
                {error}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="email" className="label">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <button
                type="submit"
                className="btn-primary w-full"
                disabled={loading}
              >
                {loading ? "Sending..." : "Send Reset Link"}
              </button>
            </form>
            <p className="text-sm text-[var(--muted)] mt-4">
              <Link
                href="/login"
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
