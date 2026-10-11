import type { FormEvent, ReactNode } from "react";
import { FormError } from "../FormError/FormError";
import type { FormProblem } from "../hooks/formProblems";
import styles from "./Form.module.css";
import { FormStatusContext } from "./status";

export interface FormProps {
  /** The form from useForm: only what the frame needs. */
  form: { submitting: boolean; problem: FormProblem | null; handleSubmit: (event?: FormEvent) => Promise<void> };
  label: string;
  children: ReactNode;
}

/** Every form: validated by its own schema (not the browser's), its failure shown once at the top. */
export function Form({ form, label, children }: FormProps) {
  return (
    <FormStatusContext.Provider value={{ submitting: form.submitting, problem: form.problem }}>
      <form className={styles.form} aria-label={label} noValidate onSubmit={form.handleSubmit}>
        <FormError problem={form.problem} />
        {children}
      </form>
    </FormStatusContext.Provider>
  );
}
