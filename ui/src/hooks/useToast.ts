import { useContext } from "react";
import { type ToastApi, ToastContext } from "../Toast/context";

/** Show a short message. Needs a ToastProvider above it: without one it fails loudly, never silently. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast needs a <ToastProvider> above it.");
  return api;
}
