import type { ReactNode } from "react";
import type { FieldBinding } from "../hooks/useForm";
import styles from "./Field.module.css";

export interface FieldProps<T> {
  field: FieldBinding<T>;
  label: string;
  hint?: ReactNode;
  /** `inline` puts the label after the control: for a checkbox or a switch. */
  layout?: "stack" | "inline";
  children: (field: FieldBinding<T>) => ReactNode;
}

/** Every input's frame: its label, the control, a hint, and its error, all wired for screen readers. */
export function Field<T>({ field, label, hint, layout = "stack", children }: FieldProps<T>) {
  return (
    <div className={styles.field} data-layout={layout} data-invalid={field.invalid || undefined}>
      <label className={styles.label} id={field.labelId} htmlFor={field.id}>{label}</label>
      <div className={styles.control}>{children(field)}</div>
      {field.error ? (
        <p className={styles.error} id={field.errorId} aria-live="polite">{field.error}</p>
      ) : (
        hint && <p className={styles.hint} id={field.hintId}>{hint}</p>
      )}
    </div>
  );
}
