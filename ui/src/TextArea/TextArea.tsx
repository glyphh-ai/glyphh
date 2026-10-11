import type { ControlProps } from "../hooks/useForm";
import styles from "./TextArea.module.css";

export interface TextAreaProps extends ControlProps<string> {
  rows?: number;
  placeholder?: string;
  disabled?: boolean;
}

/** Several lines of text: a description, instructions. */
export function TextArea({ id, name, value, invalid, describedBy, onChange, onBlur, rows = 4, ...rest }: TextAreaProps) {
  return (
    <textarea {...rest} className={styles.area} id={id} name={name} rows={rows} value={value}
      aria-invalid={invalid || undefined} aria-describedby={describedBy}
      onChange={(e) => onChange(e.target.value)} onBlur={onBlur} />
  );
}
