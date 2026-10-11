import type { ControlProps } from "../hooks/useForm";
import styles from "./TextInput.module.css";

export interface TextInputProps extends ControlProps<string> {
  type?: "text" | "email" | "url" | "search" | "tel";
  placeholder?: string;
  autoComplete?: string;
  disabled?: boolean;
}

/** A one-line text input. */
export function TextInput(props: TextInputProps) {
  const { id, name, value, invalid, describedBy, onChange, onBlur, type = "text", placeholder, autoComplete, disabled } = props;
  return (
    <input className={styles.input} id={id} name={name} type={type} value={value} placeholder={placeholder}
      autoComplete={autoComplete} disabled={disabled}
      aria-invalid={invalid || undefined} aria-describedby={describedBy}
      onChange={(e) => onChange(e.target.value)} onBlur={onBlur} />
  );
}
