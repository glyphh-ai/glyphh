import type { FormProblem } from "../hooks/formProblems";
import styles from "./FormError.module.css";

/** Why a form did not go through, with the code and trace id that find the request in the logs. */
export function FormError({ problem }: { problem: FormProblem | null }) {
  if (!problem) return null;
  return (
    <div className={styles.error} role="alert">
      <p className={styles.message}>{problem.message}</p>
      {(problem.code || problem.traceId) && (
        <p className={styles.trace}>{[problem.code, problem.traceId && `trace ${problem.traceId}`].filter(Boolean).join(" · ")}</p>
      )}
    </div>
  );
}
