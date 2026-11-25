import { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { cx } from '@/lib/cx';
import styles from './TextField.module.css';

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
  mono?: boolean;
};

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, mono = false, className, id, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const noteId = `${inputId}-note`;
  const note = error ?? hint;

  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        className={cx(styles.input, mono && styles.mono, error && styles.invalid)}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? noteId : undefined}
        {...rest}
      />
      {note && (
        <p id={noteId} className={cx(styles.note, error && styles.error)}>
          {note}
        </p>
      )}
    </div>
  );
});
