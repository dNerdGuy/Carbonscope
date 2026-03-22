import {
  type InputHTMLAttributes,
  type ReactNode,
  type ReactElement,
  useId,
  isValidElement,
  cloneElement,
} from "react";

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
  children?: ReactNode;
}

export function FormField({
  label,
  error,
  hint,
  children,
  className = "",
  ...inputProps
}: FormFieldProps) {
  const id = useId();

  // When children are provided (e.g. <select>), inject the generated id
  // so the <label htmlFor> correctly associates with the child element.
  const renderedChildren = children
    ? isValidElement(children)
      ? cloneElement(children as ReactElement<{ id?: string }>, { id })
      : children
    : null;

  return (
    <div className="space-y-1">
      <label
        htmlFor={id}
        className="block text-sm font-medium text-[var(--foreground)]"
      >
        {label}
      </label>

      {renderedChildren ?? (
        <input
          id={id}
          className={`block w-full rounded-md border px-3 py-2 text-sm ${
            error ? "border-[var(--danger)]" : "border-[var(--card-border)]"
          } ${className}`}
          aria-invalid={!!error}
          aria-describedby={
            error ? `${id}-error` : hint ? `${id}-hint` : undefined
          }
          {...inputProps}
        />
      )}

      {error && (
        <p
          id={`${id}-error`}
          className="text-sm"
          style={{ color: "var(--danger)" }}
          role="alert"
        >
          {error}
        </p>
      )}
      {!error && hint && (
        <p
          id={`${id}-hint`}
          className="text-sm"
          style={{ color: "var(--muted)" }}
        >
          {hint}
        </p>
      )}
    </div>
  );
}
