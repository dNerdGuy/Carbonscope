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
  register as apiRegister,
  type User,
} from "@/lib/api";

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
      setToken(resp.access_token);

      // Decode JWT payload to get user info (sub, company_id)
      const payload = JSON.parse(atob(resp.access_token.split(".")[1]));
      const u: User = {
        id: payload.sub,
        email,
        full_name: "",
        company_id: payload.company_id,
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
      localStorage.setItem("user", JSON.stringify(u));
      setToken(resp.access_token);
      setUser(u);
      router.push("/dashboard");
    },
    [router],
  );

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
    router.push("/login");
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
