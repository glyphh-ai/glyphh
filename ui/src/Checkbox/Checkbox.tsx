import type { ControlProps } from "../hooks/useForm";
import styles from "./Checkbox.module.css";

/** Yes or no, ticked. Its label comes from its Field (layout inline). */
export function Checkbox({ id, name, value, invalid, describedBy, onChange, onBlur, disabled }:
  ControlProps<boolean> & { disabled?: boolean }) {
  return (
    <input className={styles.box} type="checkbox" id={id} name={name} checked={value} disabled={disabled}
      aria-invalid={invalid || undefined} aria-describedby={describedBy}
      onChange={(e) => onChange(e.target.checked)} onBlur={onBlur} />
  );
}
