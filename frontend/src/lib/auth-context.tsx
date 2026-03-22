import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useNavigate, useLocation } from "@tanstack/react-router";
import {
  login as apiLogin,
  logoutApi,
  register as apiRegister,
  getProfile,
  googleVerify,
  type User,
} from "@/lib/api";
import { getQueryClient } from "@/lib/query-client";
import { useToast } from "@/components/Toast";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { search } = useLocation();

  // Verify session with server on mount — uses httpOnly cookie sent automatically
  useEffect(() => {
    getProfile()
      .then((u) => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const resp = await apiLogin(email, password);

      // If server requests MFA, redirect to MFA verification instead of granting access
      if (resp.mfa_required) {
        navigate({ to: "/mfa-verify" });
        return;
      }

      // Server sets httpOnly cookies (access_token, refresh_token) automatically
      // Use user info from login response directly
      const u: User = resp.user
        ? {
            id: resp.user.id,
            email: resp.user.email,
            full_name: resp.user.full_name ?? "",
            company_id: resp.user.company_id,
            role: resp.user.role ?? "",
          }
        : { id: "", email, full_name: "", company_id: "", role: "" };
      setUser(u);
      const redirect = new URLSearchParams(search).get("redirect");
      // Prevent open redirect: validate with URL parser, allow only relative pathsths
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
      navigate({ to: safeRedirect });
    },
    [navigate, search],
  );

  const loginWithGoogle = useCallback(
    async (credential: string) => {
      const resp = await googleVerify(credential);
      const u: User = resp.user
        ? {
            id: resp.user.id,
            email: resp.user.email,
            full_name: resp.user.full_name ?? "",
            company_id: resp.user.company_id,
            role: resp.user.role ?? "",
          }
        : { id: "", email: "", full_name: "", company_id: "", role: "" };
      setUser(u);
      navigate({ to: "/dashboard" });
    },
    [navigate],
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
      setUser(u);
      navigate({ to: "/dashboard" });
    },
    [navigate],
  );

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      // Proceed with local cleanup even if server-side logout fails
    }
    getQueryClient().clear();
    setUser(null);
    navigate({ to: "/login" });
  }, [navigate]);

  // Listen for session-expired events dispatched by the API client
  const { toast } = useToast();
  useEffect(() => {
    const onSessionExpired = () => {
      getQueryClient().clear();
      setUser(null);
      toast("Your session has expired. Please log in again.", "warning");
      navigate({ to: "/login" });
    };
    window.addEventListener("auth:session-expired", onSessionExpired);
    return () =>
      window.removeEventListener("auth:session-expired", onSessionExpired);
  }, [navigate, toast]);

  return (
    <AuthContext.Provider
      value={{ user, loading, login, loginWithGoogle, register, logout }}
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
