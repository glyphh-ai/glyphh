import { Button } from "../Button/Button";
import { useCopy } from "../hooks/useCopy";

const WORDS = { idle: "Copy", copied: "Copied", failed: "Couldn't copy" } as const;

/** Copies its text, and says so (out loud too). */
export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const { state, copy } = useCopy();
  return (
    <Button size="sm" variant="ghost" onClick={() => copy(text)} aria-live="polite">
      {state === "idle" ? label : WORDS[state]}
    </Button>
  );
}
