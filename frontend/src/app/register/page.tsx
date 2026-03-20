"use client";

import { useState } from "react";
import Link from "next/link";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import { FormField } from "@/components/FormField";
import {
  validateRegisterField,
  validateRegisterForm,
  type RegisterFormValues,
} from "@/lib/validation";
import { INDUSTRIES, REGIONS, industryLabel } from "@/lib/constants";

export default function RegisterPage() {
  useDocumentTitle("Register");
  const { register } = useAuth();
  const [form, setForm] = useState<RegisterFormValues>({
    email: "",
    password: "",
    confirmPassword: "",
    fullName: "",
    companyName: "",
    industry: "technology",
    region: "US",
  });
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  function update(field: keyof RegisterFormValues, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    // Clear field error on change
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function validateField(field: keyof RegisterFormValues, value: string) {
    const nextValues = { ...form, [field]: value };
    const err = validateRegisterField(field, nextValues);
    setFieldErrors((prev) => {
      if (!err && !prev[field]) return prev;
      if (!err) {
        const next = { ...prev };
        delete next[field];
        return next;
      }
      return { ...prev, [field]: err };
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const validationErrors = validateRegisterForm(form);
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      setError(Object.values(validationErrors)[0]);
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
        region: form.region,
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
          <FormField
            label="Full Name"
            type="text"
            className="input"
            value={form.fullName}
            onChange={(e) => update("fullName", e.target.value)}
            required
          />
          <FormField
            label="Company Name"
            type="text"
            className="input"
            value={form.companyName}
            onChange={(e) => update("companyName", e.target.value)}
            required
          />
          <FormField label="Industry">
            <select
              className="input"
              value={form.industry}
              onChange={(e) => update("industry", e.target.value)}
            >
              {INDUSTRIES.map((ind) => (
                <option key={ind} value={ind}>
                  {industryLabel(ind)}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label="Region">
            <select
              className="input"
              value={form.region}
              onChange={(e) => update("region", e.target.value)}
            >
              {REGIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </FormField>
          <FormField
            label="Email"
            type="email"
            className="input"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            onBlur={(e) => validateField("email", e.target.value)}
            error={fieldErrors.email}
            required
            autoComplete="email"
          />
          <FormField
            label="Password"
            type="password"
            className="input"
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            onBlur={(e) => validateField("password", e.target.value)}
            error={fieldErrors.password}
            required
            minLength={8}
            autoComplete="new-password"
            hint="Min 8 characters, must include an uppercase letter and a digit."
          />
          <FormField
            label="Confirm Password"
            type="password"
            className="input"
            value={form.confirmPassword}
            onChange={(e) => update("confirmPassword", e.target.value)}
            onBlur={(e) => validateField("confirmPassword", e.target.value)}
            error={fieldErrors.confirmPassword}
            required
            autoComplete="new-password"
          />
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
