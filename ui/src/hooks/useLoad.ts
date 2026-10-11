import { useCallback, useEffect, useRef, useState } from "react";
import { type FormProblem, problemsOf } from "./formProblems";

export type Load<T> =
  | { status: "loading"; data: undefined; problem: null; reload: () => void }
  | { status: "ready"; data: T; problem: null; reload: () => void }
  | { status: "failed"; data: undefined; problem: FormProblem; reload: () => void };

/** Load something for a page (the machines, the usage), with a reload. A failure is a problem to show,
 *  with its code and trace id; an answer that arrives after a newer request is dropped. */
export function useLoad<T>(load: () => Promise<T>, deps: readonly unknown[] = []): Load<T> {
  const [state, setState] = useState<Omit<Load<T>, "reload">>({ status: "loading", data: undefined, problem: null });
  const latest = useRef(0);
  const run = useCallback(() => {
    const ticket = ++latest.current;
    setState({ status: "loading", data: undefined, problem: null });
    load().then(
      (data) => { if (ticket === latest.current) setState({ status: "ready", data, problem: null }); },
      (error) => {
        if (ticket === latest.current) setState({ status: "failed", data: undefined, problem: problemsOf(error).problem ?? { message: "Something went wrong. Try again." } });
      },
    );
  }, deps);
  useEffect(() => { run(); return () => { latest.current++; }; }, [run]);
  return { ...state, reload: run } as Load<T>;
}
