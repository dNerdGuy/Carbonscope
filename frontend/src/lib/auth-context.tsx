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

function syncLoggedInCookie(loggedIn: boolean): void {
  if (typeof document === "undefined") return;
  if (!loggedIn) {
    document.cookie = "cs_access_token=; Path=/; Max-Age=0; SameSite=Lax";
    return;
  }
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `cs_access_token=1; Path=/; SameSite=Lax${secure}`;
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

      // Use user info from login response (server no longer sends raw JWT in body)
      const u: User = resp.user
        ? {
            id: resp.user.id,
            email: resp.user.email,
            full_name: resp.user.full_name ?? "",
            company_id: resp.user.company_id,
            role: resp.user.role ?? "",
          }
        : { id: "", email, full_name: "", company_id: "", role: "" };
      localStorage.setItem("user", JSON.stringify(u));
      setUser(u);
      const redirect = searchParams.get("redirect");
      // Prevent open redirect: validate with URL parser, allow only relative paths
      let safeRedirect = "/dashboard";
      if (redirect) {
        try {
          const url = new URL(redirect, window.location.origin);
          if (
            url.origin === window.location.origin &&
            url.pathname.startsWith("/")
          ) {
            safeRedirect = url.pathname + url.search + url.hash;
          }
        } catch {
          // Malformed URL — use default
        }
      }
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
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
