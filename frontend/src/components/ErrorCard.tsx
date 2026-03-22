
interface ErrorCardProps {
  message: string;
  onRetry?: () => void;
  title?: string;
}

export function ErrorCard({
  message,
  onRetry,
  title = "Something went wrong",
}: ErrorCardProps) {
  return (
    <div
      className="card border-[var(--danger)] flex flex-col items-center gap-3 py-8 text-center"
      role="alert"
    >
      <span
        aria-hidden="true"
        className="text-3xl"
        style={{ color: "var(--danger)" }}
      >
        ⚠
      </span>
      <h2 className="text-lg font-semibold text-[var(--foreground)]">
        {title}
      </h2>
      <p className="text-sm text-[var(--muted)] max-w-md">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-primary mt-2">
          Try Again
        </button>
      )}
    </div>
  );
}
