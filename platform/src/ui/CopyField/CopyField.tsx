import type { ReactNode } from 'react';
import { useCopy } from '@/lib/useCopy';
import { Icon } from '../Icon/Icon';
import styles from './CopyField.module.css';

type CopyFieldProps = {
  value: string;
  label: string;
};

/**
 * A read-only value in a box, such as an address or a key, with a Copy button. `shown` stands in for the value on
 * screen (a secret masked); Copy still copies the value. `children` sit before Copy, such as a Reveal button.
 */
export function CopyField({ value, label, shown, children }: CopyFieldProps & { shown?: string; children?: ReactNode }) {
  const { copied, copy } = useCopy();
  return (
    <div className={styles.field}>
      <span className={styles.value} title={shown === undefined ? value : undefined}>
        {shown ?? value}
      </span>
      {children}
      <button type="button" className={styles.copy} onClick={() => void copy(value)} aria-label={`Copy ${label}`}>
        <Icon name={copied ? 'check' : 'copy'} size={14} />
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  );
}

/** An icon-only copy button, for a value already shown beside it. */
export function CopyButton({ value, label }: CopyFieldProps) {
  const { copied, copy } = useCopy();
  return (
    <button type="button" className={styles.iconButton} onClick={() => void copy(value)} aria-label={copied ? 'Copied' : `Copy ${label}`}>
      <Icon name={copied ? 'check' : 'copy'} size={15} />
    </button>
  );
}
