import type { ControlProps } from "../hooks/useForm";
import type { Option } from "../Select/Select";
import styles from "./RadioGroup.module.css";

export interface RadioGroupProps extends ControlProps<string> {
  options: Option[];
  /** The Field's label id, so the group is named by it. */
  labelledBy: string;
  disabled?: boolean;
}

/** One choice, all options in view. Arrow keys move between them, as browsers do for radios. */
export function RadioGroup({ id, name, value, invalid, describedBy, onChange, onBlur, options, labelledBy, disabled }: RadioGroupProps) {
  return (
    <div className={styles.group} role="radiogroup" id={id} aria-labelledby={labelledBy}
      aria-describedby={describedBy} aria-invalid={invalid || undefined}>
      {options.map((o) => (
        <label key={o.value} className={styles.option}>
          <input type="radio" name={name} value={o.value} checked={value === o.value} disabled={disabled}
            onChange={() => onChange(o.value)} onBlur={onBlur} />
          {o.label}
        </label>
      ))}
    </div>
  );
}
