import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth-context";

/**
 * Redirects unauthenticated users to /login.
 * Returns { user, loading } from the auth context.
 */
export function useRequireAuth() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !user) {
      navigate({ to: "/login", replace: true });
    }
  }, [user, loading, navigate]);

  return { user, loading };
}
