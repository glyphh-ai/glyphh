import styles from "./ProgressSteps.module.css";

export interface Step {
  key: string;
  label: string;
}

export interface ProgressStepsProps {
  label: string;
  steps: Step[];
  /** The step happening now; those before it are done. */
  current: string;
  /** The current step failed. */
  failed?: boolean;
}

type State = "done" | "current" | "failed" | "pending";

/** Steps in order, each done, happening, failed or still to come: deploying a machine. */
export function ProgressSteps({ label, steps, current, failed = false }: ProgressStepsProps) {
  const at = steps.findIndex((s) => s.key === current);
  const stateOf = (i: number): State => (i < at ? "done" : i > at ? "pending" : failed ? "failed" : "current");
  return (
    <ol className={styles.steps} aria-label={label}>
      {steps.map((step, i) => (
        <li key={step.key} className={styles.step} data-state={stateOf(i)} aria-current={i === at ? "step" : undefined}>
          <span className={styles.marker} aria-hidden="true" />
          <span>{step.label}</span>
        </li>
      ))}
    </ol>
  );
}
