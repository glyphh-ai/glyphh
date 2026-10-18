import { Link } from 'react-router';
import { ApiError } from '@/api/client';
import type { MachineSize } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ErrorNotice, TextField } from '@/ui';
import { sizes } from './sizes';
import styles from './Machines.module.css';

type MachineFieldsProps = {
  name: string;
  size: MachineSize;
  onName: (name: string) => void;
  onSize: (size: MachineSize) => void;
};

/** A new machine's name and size: the three sizes as cards with what each one has. */
export function MachineFields({ name, size, onName, onSize }: MachineFieldsProps) {
  return (
    <>
      <TextField label="Name" value={name} onChange={(e) => onName(e.target.value)} maxLength={60} placeholder="Main" />
      <fieldset className={styles.sizes}>
        <legend className={styles.legend}>Size</legend>
        {sizes.map((option) => (
          <label key={option.value} className={styles.size}>
            <input type="radio" name="size" value={option.value} checked={size === option.value} onChange={() => onSize(option.value)} />
            <span className={styles.sizeBody}>
              <span className={styles.sizeName}>{option.label}</span>
              <span className={styles.sizeSpec}>{option.cpu}</span>
              <span className={styles.sizeSpec}>{option.ram}</span>
              <span className={styles.sizeSpec}>{option.disk}</span>
            </span>
          </label>
        ))}
      </fieldset>
    </>
  );
}

/** Why a machine was not made; at the plan's limit, the way to a bigger plan. */
export function CreateMachineError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.code === 'E_LIMIT' && error.detail.reason === 'machines') {
    return (
      <ErrorNotice
        message="Your plan has no room for another machine. Delete one, or move to a bigger plan."
        traceId={error.traceId}
        action={<Link to="/settings/billing">Billing</Link>}
      />
    );
  }
  return <ApiErrorNotice error={error} />;
}
