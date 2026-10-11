import type { ControlProps } from "../hooks/useForm";
import styles from "./Switch.module.css";

/** On or off, taking effect as a setting. Its label comes from its Field (layout inline). */
export function Switch({ id, name, value, describedBy, onChange, onBlur, disabled, labelledBy }:
  ControlProps<boolean> & { disabled?: boolean; labelledBy?: string }) {
  return (
    <button type="button" role="switch" className={styles.switch} id={id} name={name} aria-checked={value}
      aria-labelledby={labelledBy} aria-describedby={describedBy} disabled={disabled}
      onClick={() => onChange(!value)} onBlur={onBlur}>
      <span className={styles.thumb} />
    </button>
  );
}
