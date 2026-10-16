import { useState, type FormEvent } from 'react';
import { useChangeSeats } from '@/api/queries';
import type { Me } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { money } from '@/lib/format';
import { Button, Dialog, TextField } from '@/ui';

export function SeatsDialog({ me, onClose }: { me: Me; onClose: () => void }) {
  const [seats, setSeats] = useState(String(me.org.seats));
  const change = useChangeSeats();
  const count = Number.parseInt(seats, 10);
  const valid = Number.isInteger(count) && count >= Math.max(1, me.used.seats) && count <= 10000;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (valid) change.mutate(count, { onSuccess: onClose });
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="Change seats"
      description={`${me.used.seats} of ${me.org.seats} seats are taken. Each seat is ${money(me.plan.seat_price_cents)} a month, prorated by Stripe.`}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="seats" loading={change.isPending} disabled={!valid || count === me.org.seats}>
            Save
          </Button>
        </>
      }
    >
      <form id="seats" onSubmit={submit}>
        <TextField
          label="Seats"
          type="number"
          inputMode="numeric"
          min={Math.max(1, me.used.seats)}
          max={10000}
          value={seats}
          onChange={(e) => setSeats(e.target.value)}
          error={seats && !valid ? `At least ${Math.max(1, me.used.seats)}, the seats already taken.` : undefined}
        />
      </form>
      <ApiErrorNotice error={change.error} />
    </Dialog>
  );
}
