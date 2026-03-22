
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let _nextId = 0;
const TOAST_DURATION = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const scheduleRemoval = useCallback((id: number, delay: number) => {
    const timer = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
      timers.current.delete(id);
    }, delay);
    timers.current.set(id, timer);
  }, []);

  const toast = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = ++_nextId;
      setToasts((prev) => [...prev, { id, message, type }]);
      scheduleRemoval(id, TOAST_DURATION);
    },
    [scheduleRemoval],
  );

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
    timers.current.delete(id);
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const pauseTimer = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const resumeTimer = useCallback(
    (id: number) => {
      scheduleRemoval(id, TOAST_DURATION);
    },
    [scheduleRemoval],
  );

  const colors: Record<ToastType, string> = {
    success: "toast-success",
    error: "toast-error",
    warning: "toast-warning",
    info: "toast-info",
  };

  const icons: Record<ToastType, string> = {
    success: "✓",
    error: "✕",
    warning: "⚠",
    info: "ℹ",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.type === "error" ? "alert" : "status"}
            aria-live={t.type === "error" ? "assertive" : "polite"}
            className={`${colors[t.type]} px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 min-w-[280px] max-w-[400px] animate-slide-in`}
            onMouseEnter={() => pauseTimer(t.id)}
            onMouseLeave={() => resumeTimer(t.id)}
            tabIndex={0}
            onFocus={() => pauseTimer(t.id)}
            onBlur={() => resumeTimer(t.id)}
          >
            <span className="text-lg" aria-hidden="true">
              {icons[t.type]}
            </span>
            <span className="flex-1 text-sm">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="opacity-70 hover:opacity-100"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}
