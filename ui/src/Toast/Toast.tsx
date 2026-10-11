import { type ReactNode, useCallback, useMemo, useRef, useState } from "react";
import { IconButton } from "../IconButton/IconButton";
import { type ToastInput, ToastContext } from "./context";
import styles from "./Toast.module.css";

interface Shown extends ToastInput {
  id: number;
}

/** Holds the toasts for everything inside it, each gone after a few seconds (errors stay twice as long). */
export function ToastProvider({ children, durationMs = 4000 }: { children: ReactNode; durationMs?: number }) {
  const [toasts, setToasts] = useState<Shown[]>([]);
  const next = useRef(0);
  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), []);
  const show = useCallback((toast: ToastInput) => {
    const id = ++next.current;
    setToasts((all) => [...all, { ...toast, id }]);
    setTimeout(() => dismiss(id), toast.tone === "danger" ? durationMs * 2 : durationMs);
  }, [dismiss, durationMs]);
  const api = useMemo(() => ({ show }), [show]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <section className={styles.region} aria-label="Notifications">
        {toasts.map((t) => (
          <div key={t.id} className={styles.toast} data-tone={t.tone ?? "info"} role={t.tone === "danger" ? "alert" : "status"}>
            <span>{t.message}{t.traceId && <span className={styles.trace}> · trace {t.traceId}</span>}</span>
            <IconButton label="Dismiss" icon="×" onClick={() => dismiss(t.id)} />
          </div>
        ))}
      </section>
    </ToastContext.Provider>
  );
}
