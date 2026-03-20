"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  login as apiLogin,
  logoutApi,
  register as apiRegister,
  type User,
} from "@/lib/api";
import { getQueryClient } from "@/lib/query-client";
import { useToast } from "@/components/Toast";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    company_name: string;
    industry: string;
    region?: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function decodeBase64UrlPayload(raw: string): Record<string, unknown> {
  const base64 = raw.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(
    base64.length + ((4 - (base64.length % 4)) % 4),
    "=",
  );
  const decoded = atob(padded);
  return JSON.parse(decoded) as Record<string, unknown>;
}

function syncLoggedInCookie(loggedIn: boolean): void {
  if (typeof document === "undefined") return;
  if (!loggedIn) {
    document.cookie = "cs_access_token=; Path=/; Max-Age=0; SameSite=Lax";
    return;
  }
  document.cookie = "cs_access_token=1; Path=/; SameSite=Lax";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const searchParams = useSearchParams();

  // Restore user display data from localStorage on mount
  useEffect(() => {
    const savedUser = localStorage.getItem("user");
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem("user");
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const resp = await apiLogin(email, password);

      // If server requests MFA, redirect to MFA verification instead of granting access
      if (resp.mfa_required) {
        router.push("/mfa-verify");
        return;
      }

      // Server sets httpOnly cookies (access_token, refresh_token) automatically
      syncLoggedInCookie(true);

      // Decode JWT payload — handle base64url encoding (RFC 7519)
      const raw = resp.access_token.split(".")[1];
      const payload = decodeBase64UrlPayload(raw);
      const u: User = {
        id: String(payload.sub ?? ""),
        email,
        full_name: "",
        company_id: String(payload.company_id ?? ""),
        role: "",
      };
      localStorage.setItem("user", JSON.stringify(u));
      setUser(u);
      const redirect = searchParams.get("redirect");
      // Prevent open redirect: must start with single '/' and not '//'
      const safeRedirect =
        redirect && /^\/[^/\\]/.test(redirect) ? redirect : "/dashboard";
      router.push(safeRedirect);
    },
    [router, searchParams],
  );

  const register = useCallback(
    async (data: {
      email: string;
      password: string;
      full_name: string;
      company_name: string;
      industry: string;
      region?: string;
    }) => {
      const u = await apiRegister(data);
      // Auto-login after registration — server sets httpOnly cookies
      await apiLogin(data.email, data.password);
      syncLoggedInCookie(true);
      localStorage.setItem("user", JSON.stringify(u));
      setUser(u);
      router.push("/dashboard");
    },
    [router],
  );

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      // Proceed with local cleanup even if server-side logout fails
    }
    localStorage.removeItem("user");
    syncLoggedInCookie(false);
    getQueryClient().clear();
    setUser(null);
    router.push("/login");
  }, [router]);

  // Listen for session-expired events dispatched by the API client
  const { toast } = useToast();
  useEffect(() => {
    const onSessionExpired = () => {
      syncLoggedInCookie(false);
      getQueryClient().clear();
      setUser(null);
      toast("Your session has expired. Please log in again.", "warning");
      router.push("/login");
    };
    window.addEventListener("auth:session-expired", onSessionExpired);
    return () =>
      window.removeEventListener("auth:session-expired", onSessionExpired);
  }, [router, toast]);

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
