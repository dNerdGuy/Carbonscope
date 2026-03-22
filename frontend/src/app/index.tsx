import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading) {
      navigate({ to: user ? "/dashboard" : "/login", replace: true });
    }
  }, [user, loading, navigate]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-[var(--muted)]">Loading...</div>
    </div>
  );
}
