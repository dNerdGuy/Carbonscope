interface StatusMessageProps {
  message: string;
  variant: "error" | "success";
}

export function StatusMessage({ message, variant }: StatusMessageProps) {
  if (!message) return null;
  const color = variant === "error" ? "var(--danger)" : "var(--primary)";
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={`text-sm rounded-md p-3`}
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)`,
      }}
    >
      {message}
    </div>
  );
}
