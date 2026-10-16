import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';
import styles from './Chip.module.css';

export type ChipTone = 'green' | 'amber' | 'red' | 'blue' | 'violet' | 'neutral';

type ChipProps = {
  tone?: ChipTone;
  /** A small dot before the text, for live states such as Running. */
  dot?: boolean;
  mono?: boolean;
  children: ReactNode;
};

export function Chip({ tone = 'neutral', dot = false, mono = false, children }: ChipProps) {
  return (
    <span className={cx(styles.chip, styles[tone], mono && styles.mono)}>
      {dot && <span className={styles.dot} aria-hidden="true" />}
      {children}
    </span>
  );
}
