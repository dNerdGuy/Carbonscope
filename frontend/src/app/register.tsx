import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import { FormField } from "@/components/FormField";
import {
  validateRegisterField,
  validateRegisterForm,
  type RegisterFormValues,
} from "@/lib/validation";
import { INDUSTRIES, REGIONS, industryLabel } from "@/lib/constants";
import { env } from "@/lib/env";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: object) => void;
          renderButton: (el: HTMLElement, opts: object) => void;
          prompt: () => void;
        };
      };
    };
  }
}

const GIS_SCRIPT = "https://accounts.google.com/gsi/client";
const GOOGLE_CLIENT_ID = env.GOOGLE_CLIENT_ID;

export const Route = createFileRoute("/register")({ component: RegisterPage });

function RegisterPage() {
  useDocumentTitle("Register");
  const { register, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
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
  const googleBtnRef = useRef<HTMLDivElement>(null);

  // Load GIS SDK and render Google button
  useEffect(() => {
    function initGoogle() {
      if (!window.google || !googleBtnRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleCredential,
        use_fedcm_for_prompt: true,
      });
      window.google.accounts.id.renderButton(googleBtnRef.current, {
        theme: "outline",
        size: "large",
        width: googleBtnRef.current.offsetWidth || 400,
        text: "signup_with",
        shape: "rectangular",
      });
    }

    if (window.google) {
      initGoogle();
      return;
    }

    const script = document.createElement("script");
    script.src = GIS_SCRIPT;
    script.async = true;
    script.defer = true;
    script.onload = initGoogle;
    document.head.appendChild(script);

    return () => {
      const existing = document.querySelector(`script[src="${GIS_SCRIPT}"]`);
      if (existing) existing.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleGoogleCredential(response: { credential: string }) {
    setError("");
    setSubmitting(true);
    try {
      await loginWithGoogle(response.credential);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Google sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

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
          <h1 className="flex items-center justify-center gap-2 text-2xl font-bold text-[var(--primary)]">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 22c4-4 8-7.5 8-12a8 8 0 10-16 0c0 4.5 4 8 8 12z" />
              <path d="M12 10a2 2 0 100-4 2 2 0 000 4z" />
            </svg>
            CarbonScope
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
            maxLength={72}
            autoComplete="new-password"
            hint="8–72 characters, must include an uppercase letter, a digit, and a special character."
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

        {/* Google Sign-In */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-[var(--card-border)]" />
          </div>
          <div className="relative flex justify-center text-xs text-(--muted) uppercase tracking-wide">
            <span className="bg-[var(--card)] px-3">or sign up with</span>
          </div>
        </div>
        <div ref={googleBtnRef} className="w-full flex justify-center" />
        <p className="text-center text-sm text-[var(--muted)] mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-[var(--primary)] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
