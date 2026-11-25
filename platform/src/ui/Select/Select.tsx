import { useId, type SelectHTMLAttributes } from 'react';
import { Icon } from '../Icon/Icon';
import fieldStyles from '../TextField/TextField.module.css';
import styles from './Select.module.css';

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> & {
  label: string;
  hint?: string;
  /** A disabled option is shown greyed and cannot be chosen. */
  options: ReadonlyArray<{ value: string; label: string; disabled?: boolean }>;
};

/** A native select in the field's look, so the keyboard, the screen reader and the phone picker all just work. */
export function Select({ label, hint, options, id, ...rest }: SelectProps) {
  const autoId = useId();
  const selectId = id ?? autoId;
  const noteId = `${selectId}-note`;
  return (
    <div className={fieldStyles.field}>
      <label htmlFor={selectId} className={fieldStyles.label}>
        {label}
      </label>
      <div className={styles.box}>
        <select id={selectId} className={`${fieldStyles.input} ${styles.select}`} aria-describedby={hint ? noteId : undefined} {...rest}>
          {options.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.label}
            </option>
          ))}
        </select>
        <Icon name="chevronDown" size={14} className={styles.chevron} />
      </div>
      {hint && (
        <p id={noteId} className={fieldStyles.note}>
          {hint}
        </p>
      )}
    </div>
  );
}
