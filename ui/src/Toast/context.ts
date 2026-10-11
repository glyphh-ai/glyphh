import { createContext } from "react";

export interface ToastInput {
  message: string;
  tone?: "info" | "ok" | "danger";
  /** For an error: the trace id, shown so it can be quoted. */
  traceId?: string;
}

export interface ToastApi {
  show: (toast: ToastInput) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);
