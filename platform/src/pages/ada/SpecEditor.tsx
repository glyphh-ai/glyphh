import { useId } from 'react';
import { plural } from '@/lib/format';
import { rolesOf, type Checked } from '@/lib/spec';
import styles from './ada.module.css';

/** The problems shown at most; the rest are counted. */
const shown = 8;

/** A spec typed as JSON, checked as it is typed: its problems by path, or what it holds. */
export function SpecEditor({ value, onChange, checked }: { value: string; onChange: (text: string) => void; checked: Checked }) {
  const id = useId();
  const noteId = `${id}-note`;
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        Spec
      </label>
      <textarea
        id={id}
        className={styles.editor}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
        aria-invalid={checked.problems.length > 0 || undefined}
        aria-describedby={noteId}
      />
      <div id={noteId} aria-live="polite">
        {checked.spec ? (
          <p className={styles.good}>
            Looks right: {plural(rolesOf(checked.spec).length, 'role')} in {plural(checked.spec.layers.length, 'layer')}. The server checks it again.
          </p>
        ) : (
          <ul className={styles.problems} aria-label="Problems">
            {checked.problems.slice(0, shown).map((problem, i) => (
              <li key={i}>
                <code>{problem.path}</code> {problem.message}
              </li>
            ))}
            {checked.problems.length > shown && <li>and {plural(checked.problems.length - shown, 'more problem')}.</li>}
          </ul>
        )}
      </div>
    </div>
  );
}
