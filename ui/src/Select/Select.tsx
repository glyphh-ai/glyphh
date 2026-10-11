import type { ControlProps } from "../hooks/useForm";
import styles from "./Select.module.css";

export interface Option {
  value: string;
  label: string;
}

export interface SelectProps extends ControlProps<string> {
  options: Option[];
  /** Shown while nothing is chosen; it cannot be chosen itself. */
  placeholder?: string;
  disabled?: boolean;
}

/** One choice from a list. */
export function Select({ id, name, value, invalid, describedBy, onChange, onBlur, options, placeholder, disabled }: SelectProps) {
  return (
    <select className={styles.select} id={id} name={name} value={value} disabled={disabled}
      aria-invalid={invalid || undefined} aria-describedby={describedBy}
      onChange={(e) => onChange(e.target.value)} onBlur={onBlur}>
      {placeholder && <option value="" disabled>{placeholder}</option>}
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}
