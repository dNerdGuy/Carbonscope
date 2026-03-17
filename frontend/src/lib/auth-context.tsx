"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  login as apiLogin,
  logoutApi,
  register as apiRegister,
  type User,
} from "@/lib/api";
import { getQueryClient } from "@/lib/query-client";

interface AuthState {
  user: User | null;
  token: string | null;
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

function syncClientAuthCookie(token: string | null): void {
  if (typeof document === "undefined") return;
  if (!token) {
    document.cookie = "cs_access_token=; Path=/; Max-Age=0; SameSite=Lax";
    return;
  }
  document.cookie = `cs_access_token=${encodeURIComponent(token)}; Path=/; SameSite=Lax`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Restore from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("token");
    const savedUser = localStorage.getItem("user");
    if (saved && savedUser) {
      setToken(saved);
      syncClientAuthCookie(saved);
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
      localStorage.setItem("token", resp.access_token);
      if (resp.refresh_token) {
        localStorage.setItem("refresh_token", resp.refresh_token);
      }
      setToken(resp.access_token);
      syncClientAuthCookie(resp.access_token);

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
      router.push("/dashboard");
    },
    [router],
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
      // Auto-login after registration
      const resp = await apiLogin(data.email, data.password);
      localStorage.setItem("token", resp.access_token);
      if (resp.refresh_token) {
        localStorage.setItem("refresh_token", resp.refresh_token);
      }
      localStorage.setItem("user", JSON.stringify(u));
      setToken(resp.access_token);
      setUser(u);
      syncClientAuthCookie(resp.access_token);
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
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    syncClientAuthCookie(null);
    getQueryClient().clear();
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  // Listen for session-expired events dispatched by the API client
  useEffect(() => {
    const onSessionExpired = () => {
      syncClientAuthCookie(null);
      getQueryClient().clear();
      setToken(null);
      setUser(null);
      router.push("/login");
    };
    window.addEventListener("auth:session-expired", onSessionExpired);
    return () =>
      window.removeEventListener("auth:session-expired", onSessionExpired);
  }, [router]);

  return (
    <AuthContext.Provider
      value={{ user, token, loading, login, register, logout }}
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
