import { useEffect, useRef, useState } from "react";

export type CopyState = "idle" | "copied" | "failed";

/** Copy text to the clipboard, and say for a moment whether it worked. */
export function useCopy(resetAfterMs = 2000): { state: CopyState; copy: (text: string) => Promise<void> } {
  const [state, setState] = useState<CopyState>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), resetAfterMs);
  };

  return { state, copy };
}
