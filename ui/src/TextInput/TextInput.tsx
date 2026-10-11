import type { ControlProps } from "../hooks/useForm";
import styles from "./TextInput.module.css";

export interface TextInputProps extends ControlProps<string> {
  type?: "text" | "email" | "url" | "search" | "tel";
  placeholder?: string;
  autoComplete?: string;
  disabled?: boolean;
}

/** A one-line text input. */
export function TextInput({ id, name, value, invalid, describedBy, onChange, onBlur, type = "text", ...rest }: TextInputProps) {
  return (
    <input {...rest} className={styles.input} id={id} name={name} type={type} value={value}
      aria-invalid={invalid || undefined} aria-describedby={describedBy}
      onChange={(e) => onChange(e.target.value)} onBlur={onBlur} />
  );
}
