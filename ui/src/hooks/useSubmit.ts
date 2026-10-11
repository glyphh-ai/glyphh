import { useRef, useState } from "react";
import { type FormProblem, type Problems, problemsOf } from "./formProblems";

export interface Submit<T> {
  submitting: boolean;
  problem: FormProblem | null;
  /** Runs `send` once at a time: a second call while one is in flight does nothing. */
  run: (value: T) => Promise<Problems | null>;
}

/** Sending, once at a time, and what came back when it failed. */
export function useSubmit<T>(send: (value: T) => Promise<void>): Submit<T> {
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<FormProblem | null>(null);
  const busy = useRef(false);

  const run = async (value: T): Promise<Problems | null> => {
    if (busy.current) return null;
    busy.current = true;
    setSubmitting(true);
    setProblem(null);
    try {
      await send(value);
      return null;
    } catch (error) {
      const found = problemsOf(error);
      setProblem(found.problem);
      return found;
    } finally {
      busy.current = false;
      setSubmitting(false);
    }
  };

  return { submitting, problem, run };
}
