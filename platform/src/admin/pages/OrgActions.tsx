import { useState } from 'react';
import {
  useAdminPlans,
  useChangePlan,
  useGrantBalance,
  useGrantEnterprise,
  useRevokeEnterprise,
  useSuspend,
  useUnsuspend,
  type OrgDetail,
} from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { dollarsToCents, money } from '@/lib/format';
import { Button, Card, Dialog, Select, TextField, useToast } from '@/ui';
import styles from '../admin.module.css';

type Open = 'plan' | 'grant' | 'revoke' | 'suspend' | 'lift' | 'balance' | null;

/** The staff actions on one org, each audited by the server with what it changed. */
export function OrgActions({ org }: { org: OrgDetail['account'] }) {
  const [open, setOpen] = useState<Open>(null);
  const close = () => setOpen(null);
  const enterprise = org.plan === 'Enterprise';
  return (
    <Card>
      <h2 className={styles.cardTitle}>Staff actions</h2>
      <div className={styles.actions}>
        <Button onClick={() => setOpen('plan')}>Change plan version</Button>
        {enterprise ? <Button onClick={() => setOpen('revoke')}>Revoke Enterprise</Button> : <Button onClick={() => setOpen('grant')}>Grant Enterprise</Button>}
        <Button onClick={() => setOpen('balance')}>Grant balance</Button>
        {org.suspended_at ? (
          <Button onClick={() => setOpen('lift')}>Lift suspension</Button>
        ) : (
          <Button variant="danger" onClick={() => setOpen('suspend')}>
            Suspend
          </Button>
        )}
      </div>
      {open === 'plan' && <PlanDialog org={org} onClose={close} />}
      {open === 'grant' && <GrantDialog org={org} onClose={close} />}
      {open === 'suspend' && <SuspendDialog org={org} onClose={close} />}
      {open === 'revoke' && <RevokeDialog org={org} onClose={close} />}
      {open === 'lift' && <LiftDialog org={org} onClose={close} />}
      {open === 'balance' && <BalanceDialog org={org} onClose={close} />}
    </Card>
  );
}

type DialogProps = { org: OrgDetail['account']; onClose: () => void };

function PlanDialog({ org, onClose }: DialogProps) {
  const toast = useToast();
  const plans = useAdminPlans();
  const change = useChangePlan(org.id);
  const [chosen, setChosen] = useState(org.plan_version_id);
  const options = (plans.data ?? []).flatMap((p) =>
    p.versions.map((v) => ({ value: v.id, label: `${p.name} v${v.version}${v.newest ? ' (newest)' : ''}, ${v.orgs} orgs` })),
  );
  const save = () => change.mutate(chosen, { onSuccess: (done) => (toast.show(done.message), onClose()) });
  return (
    <Dialog
      open
      onClose={onClose}
      title="Change plan version"
      description="Within the plan the org pays for, or with no subscription, to any self-serve plan. Enterprise is granted, never set here."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={change.isPending} disabled={chosen === org.plan_version_id} onClick={save}>
            Change
          </Button>
        </>
      }
    >
      <Select label="Plan version" value={chosen} options={options} onChange={(e) => setChosen(e.target.value)} />
      <ApiErrorNotice error={change.error ?? plans.error} />
    </Dialog>
  );
}

function GrantDialog({ org, onClose }: DialogProps) {
  const toast = useToast();
  const grant = useGrantEnterprise(org.id);
  const [until, setUntil] = useState('');
  const [subscription, setSubscription] = useState('');
  const ready = /^\d{4}-\d{2}-\d{2}$/.test(until) && /^sub_\w+$/.test(subscription.trim());
  const save = () =>
    grant.mutate({ until, subscription: subscription.trim() }, { onSuccess: (done) => (toast.show(done.message), onClose()) });
  return (
    <Dialog
      open
      onClose={onClose}
      title="Grant Enterprise"
      description="On Enterprise through the deal’s last day, billed on its Stripe subscription, with a licence key to then."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={grant.isPending} disabled={!ready} onClick={save}>
            Grant
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <TextField label="Last day" type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
        <TextField label="Stripe subscription" mono placeholder="sub_…" value={subscription} onChange={(e) => setSubscription(e.target.value)} />        <ApiErrorNotice error={grant.error} />
      </div>
    </Dialog>
  );
}

/** The most one grant may add, in cents: $10,000. */
const maxGrantCents = 1_000_000;

/** Adds dollars to the org's overage balance for its hosted models, as a grant, with why. */
function BalanceDialog({ org, onClose }: DialogProps) {
  const toast = useToast();
  const grant = useGrantBalance(org.id);
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const cents = dollarsToCents(amount);
  const ready = cents !== null && cents > 0 && cents <= maxGrantCents && note.trim().length >= 3;
  const save = () => {
    if (cents !== null) grant.mutate({ amount_cents: cents, note: note.trim() }, { onSuccess: (done) => (toast.show(done.message), onClose()) });
  };
  return (
    <Dialog
      open
      onClose={onClose}
      title="Grant balance"
      description={`Adds dollars to ${org.name}’s overage balance for hosted models, kept in its balance history as a grant.`}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={grant.isPending} disabled={!ready} onClick={save}>
            {ready ? `Grant ${money(cents)}` : 'Grant'}
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <TextField label="Amount in dollars" inputMode="decimal" hint={`Up to ${money(maxGrantCents)}`} value={amount} onChange={(e) => setAmount(e.target.value)} />
        <TextField label="Note" hint="Shown in the org’s balance history and the audit log" value={note} onChange={(e) => setNote(e.target.value)} />
        <ApiErrorNotice error={grant.error} />
      </div>
    </Dialog>
  );
}

function SuspendDialog({ org, onClose }: DialogProps) {
  const toast = useToast();
  const suspend = useSuspend(org.id);
  const [reason, setReason] = useState('');
  const save = () => suspend.mutate(reason.trim(), { onSuccess: () => (toast.show(`${org.name} is suspended.`), onClose()) });
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Suspend ${org.name}`}
      description="Its people, its connector and its API keys are refused until the suspension is lifted. Nothing of its data changes."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" loading={suspend.isPending} disabled={reason.trim().length < 3} onClick={save}>
            Suspend
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <TextField label="Reason" hint="Kept with the suspension and in the audit log" value={reason} onChange={(e) => setReason(e.target.value)} />
        <ApiErrorNotice error={suspend.error} />
      </div>
    </Dialog>
  );
}

function RevokeDialog({ org, onClose }: DialogProps) {
  const toast = useToast();
  const revoke = useRevokeEnterprise(org.id);
  return (
    <ConfirmDialog
      open
      title="Revoke Enterprise"
      description={`${org.name} goes back on Free, its licence keys revoked. Cancel its subscription in Stripe afterwards.`}
      confirmLabel="Revoke"
      pending={revoke.isPending}
      error={revoke.error}
      onConfirm={() => revoke.mutate(undefined, { onSuccess: (done) => (toast.show(done.message), onClose()) })}
      onClose={onClose}
    />
  );
}

function LiftDialog({ org, onClose }: DialogProps) {
  const toast = useToast();
  const lift = useUnsuspend(org.id);
  return (
    <ConfirmDialog
      open
      title="Lift the suspension"
      description={`${org.name}’s people, connector and API keys work again.`}
      confirmLabel="Lift"
      pending={lift.isPending}
      error={lift.error}
      onConfirm={() => lift.mutate(undefined, { onSuccess: () => (toast.show(`${org.name} is no longer suspended.`), onClose()) })}
      onClose={onClose}
    />
  );
}
