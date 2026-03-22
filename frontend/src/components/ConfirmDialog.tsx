
import { useCallback, useRef, useEffect, type ReactNode } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
  children,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
      // Focus the cancel button when dialog opens for safer default
      cancelRef.current?.focus();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
        return;
      }
      // Focus trap: Tab cycles within dialog
      if (e.key === "Tab") {
        const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href]:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])',
        );
        if (!focusable || focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [onCancel],
  );

  if (!open) return null;

  const confirmClass =
    variant === "danger"
      ? "btn-danger"
      : "bg-[var(--primary)] hover:opacity-90 text-black";

  return (
    <dialog
      ref={dialogRef}
      onKeyDown={handleKeyDown}
      className="fixed inset-0 z-50 m-auto rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-0 shadow-2xl backdrop:bg-black/50"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-message"
    >
      <div className="p-6 max-w-md">
        <h3
          id="confirm-title"
          className="text-lg font-semibold text-[var(--foreground)]"
        >
          {title}
        </h3>
        <p id="confirm-message" className="mt-2 text-sm text-[var(--muted)]">
          {message}
        </p>
        {children}
        <div className="mt-6 flex justify-end gap-3">
          <button
            ref={cancelRef}
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm border border-[var(--card-border)] text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
