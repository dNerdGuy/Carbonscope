import {
  createFileRoute,
  Link,
  useNavigate,
  useLocation,
} from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import { FormField } from "@/components/FormField";
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

export const Route = createFileRoute("/login")({ component: LoginPage });

function LoginPage() {
  useDocumentTitle("Login");
  const { login, loginWithGoogle } = useAuth();
  const { search } = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const googleBtnRef = useRef<HTMLDivElement>(null);

  // Show error passed from OAuth callback redirect
  useEffect(() => {
    const oauthError = new URLSearchParams(search).get("error");
    if (oauthError) setError(oauthError);
  }, [search]);

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
        text: "signin_with",
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
          <div className="space-y-1">
            <label className="block text-sm font-medium text-(--foreground)">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                className="input block w-full pr-10"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-(--muted) hover:text-(--foreground) transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
                    <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="btn-primary w-full"
            disabled={submitting}
          >
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>

        {/* Google Sign-In */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-[var(--card-border)]" />
          </div>
          <div className="relative flex justify-center text-xs text-(--muted) uppercase tracking-wide">
            <span className="bg-[var(--card)] px-3">or</span>
          </div>
        </div>
        <div ref={googleBtnRef} className="w-full flex justify-center" />
        <div className="flex justify-between text-sm text-[var(--muted)] mt-6">
          <Link
            to="/forgot-password"
            className="text-[var(--primary)] hover:underline"
          >
            Forgot password?
          </Link>
          <span>
            Don&apos;t have an account?{" "}
            <Link
              to="/register"
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
