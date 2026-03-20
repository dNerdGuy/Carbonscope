"use client";

import { useState } from "react";
import Link from "next/link";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import { FormField } from "@/components/FormField";

export default function LoginPage() {
  useDocumentTitle("Login");
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      if (err instanceof Error && "status" in err) {
        const status = (err as { status: number }).status;
        if (status === 429) {
          setError("Too many requests. Please wait and try again.");
        } else if (status === 401) {
          setError("Invalid email or password.");
        } else {
          setError(err.message);
        }
      } else {
        setError(err instanceof Error ? err.message : "Login failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen px-4">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[var(--primary)]">
            🌿 CarbonScope
          </h1>
          <p className="text-[var(--muted)] mt-1">Sign in to your account</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-sm text-[var(--danger)] bg-[var(--danger)]/10 rounded-md p-3">
              {error}
            </div>
          )}
          <FormField
            label="Email"
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <FormField
            label="Password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
          <button
            type="submit"
            className="btn-primary w-full"
            disabled={submitting}
          >
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
        <div className="flex justify-between text-sm text-[var(--muted)] mt-6">
          <Link
            href="/forgot-password"
            className="text-[var(--primary)] hover:underline"
          >
            Forgot password?
          </Link>
          <span>
            Don&apos;t have an account?{" "}
            <Link
              href="/register"
              className="text-[var(--primary)] hover:underline"
            >
              Register
            </Link>
          </span>
        </div>
      </div>
    </div>
  );
}
