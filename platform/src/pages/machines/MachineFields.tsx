import { Link } from 'react-router';
import { ApiError } from '@/api/client';
import type { MachineSize, SizeRate } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { usd } from '@/lib/format';
import { ErrorNotice, TextField } from '@/ui';
import { sizes } from './sizes';
import styles from './Machines.module.css';

type MachineFieldsProps = {
  name: string;
  size: MachineSize;
  onName: (name: string) => void;
  onSize: (size: MachineSize) => void;
  /** The plan's rates, once read: each size card shows what it costs a month. */
  rates?: SizeRate[];
};

/** A new machine's name and size: the three sizes as cards with what each one has, and the plan's rate for it. */
export function MachineFields({ name, size, onName, onSize, rates }: MachineFieldsProps) {
  return (
    <>
      <TextField label="Name" value={name} onChange={(e) => onName(e.target.value)} maxLength={60} placeholder="Main" />
      <fieldset className={styles.sizes}>
        <legend className={styles.legend}>Size</legend>
        {sizes.map((option) => {
          const rate = rates?.find((r) => r.size === option.value);
          return (
            <label key={option.value} className={styles.size}>
              <input type="radio" name="size" value={option.value} checked={size === option.value} onChange={() => onSize(option.value)} />
              <span className={styles.sizeBody}>
                <span className={styles.sizeName}>{option.label}</span>
                <span className={styles.sizeSpec}>{option.cpu}</span>
                <span className={styles.sizeSpec}>{option.ram}</span>
                <span className={styles.sizeSpec}>{option.disk}</span>
                {rate && <span className={styles.sizeRate}>{`${usd(rate.usd_per_month)} / month`}</span>}
              </span>
            </label>
          );
        })}
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
