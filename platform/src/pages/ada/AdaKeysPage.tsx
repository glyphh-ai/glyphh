import { useState, type FormEvent } from 'react';
import { useCloudKeys, useCreateCloudKey, useRevokeCloudKey, type CloudKey, type NewCloudKey } from '@/api/ada';
import { useSession } from '@/api/session';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { List, Row } from '@/components/List';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, Chip, CopyField, Dialog, EmptyState, ErrorNotice, LoadingCard, Select, TextField } from '@/ui';
import styles from './ada.module.css';

/** A key lasts up to a year, or never expires; never gets a warning before it is made. */
const lifetimes = [
  { value: '7', label: '7 days' },
  { value: '30', label: '30 days' },
  { value: '60', label: '60 days' },
  { value: '90', label: '90 days' },
  { value: '365', label: '1 year' },
  { value: 'never', label: 'Never' },
] as const;

function keyStatus(key: CloudKey, now: Date) {
  const made = `Clearance ${key.clearance} · made ${date(key.created_at)}`;
  if (key.revoked_at) return { chip: <Chip tone="red">Revoked</Chip>, meta: `${made} · revoked ${date(key.revoked_at)}`, live: false };
  if (key.expires_at === null) return { chip: <Chip tone="amber">Never expires</Chip>, meta: made, live: true };
  if (new Date(key.expires_at) <= now) return { chip: <Chip tone="amber">Expired</Chip>, meta: `${made} · expired ${date(key.expires_at)}`, live: false };
  return { chip: null, meta: `${made} · expires ${date(key.expires_at)}`, live: true };
}

/** API Keys, with Ada Cloud on: keys your apps call Ada with, each with a clearance, shown once. */
export function AdaKeysPage() {
  const keys = useCloudKeys();
  const session = useSession();
  const [making, setMaking] = useState(false);
  const [revoking, setRevoking] = useState<CloudKey | null>(null);
  const revoke = useRevokeCloudKey();
  const address = session.data?.adaUrl ?? 'Ada';

  const newKey = (
    <Button variant="primary" icon="plus" onClick={() => setMaking(true)}>
      New API key
    </Button>
  );

  return (
    <>
      <PageHeader
        title="API Keys"
        description={`Your apps call ${address} with an API key as the bearer. Each key is shown once, when you make it.`}
        actions={newKey}
      />
      {keys.isPending && <LoadingCard />}
      <ApiErrorNotice error={keys.error} />
      {keys.data?.length === 0 && (
        <EmptyState icon="key" title="No API keys yet" action={newKey}>
          Make one for each app that calls Ada, so you can revoke one without the others.
        </EmptyState>
      )}
      {keys.data && keys.data.length > 0 && (
        <List label="API keys">
          {keys.data.map((key) => {
            const status = keyStatus(key, new Date());
            return (
              <Row
                key={key.id}
                title={key.name}
                badges={status.chip}
                meta={status.meta}
                actions={
                  status.live && (
                    <Button size="sm" variant="danger" onClick={() => setRevoking(key)}>
                      Revoke
                    </Button>
                  )
                }
              />
            );
          })}
        </List>
      )}

      {making && <NewKeyDialog onClose={() => setMaking(false)} />}

      <ConfirmDialog
        open={revoking !== null}
        title="Revoke this API key?"
        description={
          <>
            Apps using <strong>{revoking?.name}</strong> stop reaching Ada within seconds. This cannot be undone.
          </>
        }
        confirmLabel="Revoke"
        pending={revoke.isPending}
        error={revoke.error}
        onConfirm={() => revoking && revoke.mutate(revoking.id, { onSuccess: () => setRevoking(null) })}
        onClose={() => {
          revoke.reset();
          setRevoking(null);
        }}
      />
    </>
  );
}

/** Name a key, its expiry and clearance, then show it once. */
function NewKeyDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateCloudKey();
  const [name, setName] = useState('');
  const [days, setDays] = useState('30');
  const [clearance, setClearance] = useState('1');
  const [made, setMade] = useState<NewCloudKey | null>(null);
  const level = Number(clearance);
  const badClearance = clearance.trim() === '' || !(level >= 0 && level <= 1) ? 'A number from 0 to 1.' : undefined;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({ name: name.trim(), expires_in_days: days === 'never' ? null : Number(days), clearance: level }, { onSuccess: setMade });
  };

  if (made) {
    return (
      <Dialog
        open
        onClose={onClose}
        title="Your new API key"
        description={`Copy it now and keep it somewhere safe. You won’t see it again. ${made.expires_at ? `It expires ${date(made.expires_at)}.` : 'It never expires.'}`}
        actions={
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        }
      >
        <CopyField value={made.key} label="API key" />
      </Dialog>
    );
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title="New API key"
      description="Name it after the app that will use it."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="new-key" loading={create.isPending} disabled={!name.trim() || Boolean(badClearance)}>
            Make key
          </Button>
        </>
      }
    >
      <form id="new-key" className={styles.form} onSubmit={submit}>
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Billing worker" autoFocus />
        <Select label="Expires after" value={days} onChange={(e) => setDays(e.target.value)} options={lifetimes} />
        <TextField
          label="Clearance"
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={clearance}
          onChange={(e) => setClearance(e.target.value)}
          hint="1 reads every role. A role a spec secures above the key’s clearance is hidden from its calls."
          error={badClearance}
        />
        {days === 'never' && (
          <ErrorNotice message="This key never expires. If it leaks, it works until you revoke it. Choose an expiry unless you must." />
        )}
        <ApiErrorNotice error={create.error} />
      </form>
    </Dialog>
  );
}
