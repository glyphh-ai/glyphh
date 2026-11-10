import { useState } from 'react';
import { useTopUp } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { money } from '@/lib/format';
import { Button, Dialog, TextField } from '@/ui';
import styles from './tokens.module.css';

/** The amounts offered, in cents: $10, $25, $50 and $100. */
export const presets = [1_000, 2_500, 5_000, 10_000];
export const minCents = 1_000;
export const maxCents = 100_000;

/** "12" or "12.50" as cents; anything else (or more than two decimals) is null. */
export function dollarsToCents(text: string): number | null {
  const trimmed = text.trim().replace(/^\$/, '').replaceAll(',', '');
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  return Math.round(Number(trimmed) * 100);
}

/**
 * Add funds to the overage balance: one of the presets or another amount from $10 to $1,000, paid in Stripe's checkout
 * (the browser goes there); the balance is credited once Stripe says the payment is made.
 */
export function AddFundsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const topUp = useTopUp();
  const [preset, setPreset] = useState<number | null>(2_500);
  const [other, setOther] = useState('');

  const typed = other.trim() === '' ? null : dollarsToCents(other);
  const cents = other.trim() === '' ? preset : typed;
  const valid = cents !== null && cents >= minCents && cents <= maxCents;
  const otherError = other.trim() !== '' && !valid ? `Between ${money(minCents)} and ${money(maxCents)}, in dollars and cents.` : undefined;

  const close = () => {
    topUp.reset();
    onClose();
  };
  const pay = () => {
    if (valid) topUp.mutate(cents, { onSuccess: ({ url }) => window.location.assign(url) });
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Add funds"
      description="Past your plan’s tokens a month, hosted models are charged to this balance at each model’s rates. You pay in Stripe’s checkout; the funds are added once the payment clears."
      actions={
        <>
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!valid} loading={topUp.isPending} onClick={pay}>
            {valid ? `Add ${money(cents)}` : 'Add funds'}
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <div className={styles.presets} role="group" aria-label="Amount">
          {presets.map((amount) => (
            <Button
              key={amount}
              variant={other.trim() === '' && preset === amount ? 'primary' : 'secondary'}
              aria-pressed={other.trim() === '' && preset === amount}
              onClick={() => {
                setPreset(amount);
                setOther('');
              }}
            >
              {money(amount)}
            </Button>
          ))}
        </div>
        <TextField
          label="Another amount"
          inputMode="decimal"
          placeholder="$"
          hint={`${money(minCents)} to ${money(maxCents)}`}
          error={otherError}
          value={other}
          onChange={(event) => setOther(event.target.value)}
        />
        <ApiErrorNotice error={topUp.error} />
      </div>
    </Dialog>
  );
}
