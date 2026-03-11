"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

const INDUSTRIES = [
  "Energy",
  "Manufacturing",
  "Technology",
  "Transportation",
  "Retail",
  "Healthcare",
  "Finance",
  "Construction",
  "Agriculture",
  "Other",
];

export default function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    fullName: "",
    companyName: "",
    industry: "Technology",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (!/[A-Z]/.test(form.password) || !/\d/.test(form.password)) {
      setError(
        "Password must contain at least one uppercase letter and one digit",
      );
      return;
    }
    setSubmitting(true);
    try {
      await register({
        email: form.email,
        password: form.password,
        full_name: form.fullName,
        company_name: form.companyName,
        industry: form.industry,
      });
    } catch (err: unknown) {
      if (err instanceof Error && "status" in err) {
        const status = (err as { status: number }).status;
        if (status === 429) {
          setError("Too many requests. Please wait and try again.");
        } else if (status === 409) {
          setError("An account with this email already exists.");
        } else {
          setError(err.message);
        }
      } else {
        setError(err instanceof Error ? err.message : "Registration failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen px-4 py-8">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[var(--primary)]">
            🌿 CarbonScope
          </h1>
          <p className="text-[var(--muted)] mt-1">Create your account</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-sm text-[var(--danger)] bg-[var(--danger)]/10 rounded-md p-3">
              {error}
            </div>
          )}
          <div>
            <label className="label">Full Name</label>
            <input
              type="text"
              className="input"
              value={form.fullName}
              onChange={(e) => update("fullName", e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">Company Name</label>
            <input
              type="text"
              className="input"
              value={form.companyName}
              onChange={(e) => update("companyName", e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">Industry</label>
            <select
              className="input"
              value={form.industry}
              onChange={(e) => update("industry", e.target.value)}
            >
              {INDUSTRIES.map((ind) => (
                <option key={ind} value={ind.toLowerCase()}>
                  {ind}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Email</label>
            <input
              type="email"
              className="input"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              type="password"
              className="input"
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
            <p className="text-xs text-[var(--muted)] mt-1">
              Min 8 characters, must include an uppercase letter and a digit.
            </p>
          </div>
          <div>
            <label className="label">Confirm Password</label>
            <input
              type="password"
              className="input"
              value={form.confirmPassword}
              onChange={(e) => update("confirmPassword", e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            className="btn-primary w-full"
            disabled={submitting}
          >
            {submitting ? "Creating account..." : "Create Account"}
          </button>
        </form>
        <p className="text-center text-sm text-[var(--muted)] mt-6">
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--primary)] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
