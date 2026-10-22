import type { LeverValue } from '@/api/ada';
import { leverOf, type Lever } from '@/lib/spec';
import { Select, Switch, TextField } from '@/ui';
import styles from '../ada.module.css';

/** A lever's value while it is typed: a number's text (empty: none), a choice, or a switch. */
export type Draft = string | boolean;

export const draftOf = (value: LeverValue): Draft => (typeof value === 'boolean' ? value : value === null ? '' : String(value));

/** The lever the platform knows by name, or one read from its value (a lever this platform has no words for). */
export function leverFor(name: string, value: LeverValue): Lever {
  return leverOf(name) ?? { name, label: name, about: '', kind: typeof value === 'boolean' ? 'bool' : 'float', effect: 'live' };
}

/** One lever's control: a switch, a choice, or a number with its range. */
export function LeverInput({ lever, value, onChange, error }: { lever: Lever; value: Draft; onChange: (value: Draft) => void; error?: string }) {
  if (lever.kind === 'bool') {
    return <Switch checked={value === true} onChange={onChange} label={lever.label} />;
  }
  if (lever.kind === 'choice') {
    return (
      <div className={styles.leverInput}>
        <Select label={lever.label} value={String(value)} onChange={(e) => onChange(e.target.value)} options={lever.choices!.map((c) => ({ value: c, label: c }))} />
      </div>
    );
  }
  return (
    <div className={styles.leverInput}>
      <TextField
        label={lever.label}
        type="number"
        inputMode="decimal"
        min={lever.min}
        max={lever.max}
        step={lever.step ?? (lever.kind === 'int' ? 1 : 'any')}
        value={String(value)}
        onChange={(e) => onChange(e.target.value)}
        placeholder={lever.optional ? 'None' : undefined}
        error={error}
      />
    </div>
  );
}
