import type { ErrorComponentProps } from "@tanstack/react-router";
import { useEffect } from "react";

export default function RouteError({ error, reset }: ErrorComponentProps) {
  useEffect(() => {
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="p-8">
      <div className="card max-w-lg mx-auto text-center p-8">
        <div className="text-4xl mb-4">⚠️</div>
        <h2 className="text-xl font-bold mb-2 text-(--foreground)">
          Something went wrong
        </h2>
        <p className="text-(--muted) mb-6 text-sm">
          {error?.message || "An unexpected error occurred."}
        </p>
        <button onClick={reset} className="btn-primary">
          Retry
        </button>
      </div>
    </div>
  );
}
