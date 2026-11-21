import { useId, type TextareaHTMLAttributes } from 'react';
import type { RunStatus } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import { randomLook, type Look } from '@/bots/cat/look';
import { Button, Chip, type ChipTone } from '@/ui';
import styles from './bots.module.css';

export const botPath = (slug: string) => `/bots/${encodeURIComponent(slug)}`;

/** A bot's cat on its ink tile. */
export function CatTile({ look, size = 56, busy, label }: { look: Look | null | undefined; size?: number; busy?: boolean; label?: string }) {
  return (
    <span className={styles.catTile}>
      <Cat look={look} size={size} busy={busy} label={label} />
    </span>
  );
}

/** The cat, with Shuffle for another. */
export function CatPicker({ look, onChange }: { look: Look; onChange: (look: Look) => void }) {
  return (
    <div className={styles.row}>
      <CatTile look={look} size={72} label="The bot's cat" />
      <Button variant="secondary" size="sm" onClick={() => onChange(randomLook())}>
        Shuffle
      </Button>
    </div>
  );
}

const tones: Record<RunStatus, ChipTone> = { queued: 'neutral', running: 'blue', done: 'green', failed: 'red' };
const words: Record<RunStatus, string> = { queued: 'Queued', running: 'Running', done: 'Done', failed: 'Failed' };

export function RunChip({ status }: { status: RunStatus }) {
  return <Chip tone={tones[status]}>{words[status]}</Chip>;
}

type AreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; hint?: string };

/** A labelled text area, as TextField is for one line. */
export function TextArea({ label, hint, id, ...rest }: AreaProps) {
  const own = useId();
  const fieldId = id ?? own;
  return (
    <div className={styles.field}>
      <label htmlFor={fieldId} className={styles.label}>
        {label}
      </label>
      <textarea id={fieldId} className={styles.textarea} {...rest} />
      {hint && <span className={styles.muted}>{hint}</span>}
    </div>
  );
}
