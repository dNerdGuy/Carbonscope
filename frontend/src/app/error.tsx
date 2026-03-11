"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-8">
      <div className="card max-w-md w-full text-center p-8">
        <div className="text-4xl mb-4">⚠️</div>
        <h2 className="text-xl font-bold mb-2 text-[var(--foreground)]">
          Something went wrong
        </h2>
        <p className="text-[var(--muted)] mb-6 text-sm">
          {error.message || "An unexpected error occurred."}
        </p>
        <button onClick={reset} className="btn-primary">
          Try again
        </button>
      </div>
    </div>
  );
}
