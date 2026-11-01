import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { useAdaCloud } from '@/api/ada';
import { useCreateRuntimeKey, useDeleteRuntimeKey, useRevokeRuntimeKey, useRuntimeKeys, useSelfRuntimes } from '@/api/queries';
import type { NewRuntimeKey, RuntimeKey } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { List, Row } from '@/components/List';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, date, plural } from '@/lib/format';
import { Button, Chip, CopyField, Dialog, EmptyState, ErrorNotice, LoadingCard, Select, TextField } from '@/ui';
import styles from './KeysPage.module.css';

/** A key lasts up to a year, or never expires; never gets a warning before it is made. */
const lifetimes = [
  { value: '7', label: '7 days' },
  { value: '30', label: '30 days' },
  { value: '60', label: '60 days' },
  { value: '90', label: '90 days' },
  { value: '365', label: '1 year' },
  { value: 'never', label: 'Never' },
] as const;

/** How much a key is used: its calls and the last of them, or that it has not been used. */
function usage(key: RuntimeKey): string {
  if (key.calls === 0 || !key.last_used_at) return 'not used yet';
  return `${plural(key.calls, 'call')} · last used ${ago(key.last_used_at)}`;
}

function keyStatus(key: RuntimeKey, now: Date) {
  const made = `Made ${date(key.created_at)}`;
  if (key.revoked_at) return { chip: <Chip tone="red">Revoked</Chip>, meta: `${made} · revoked ${date(key.revoked_at)}`, live: false };
  if (key.expires_at === null) return { chip: <Chip tone="amber">Never expires</Chip>, meta: made, live: true };
  if (new Date(key.expires_at) <= now) return { chip: <Chip tone="amber">Expired</Chip>, meta: `${made} · expired ${date(key.expires_at)}`, live: false };
  return { chip: null, meta: `${made} · expires ${date(key.expires_at)}`, live: true };
}

/** The keys that call the org's self-hosted runtimes; with Ada Cloud on, Runtime keys beside Ada's own API keys. */
export function KeysPage() {
  const ada = useAdaCloud() === true;
  const keys = useRuntimeKeys();
  const [making, setMaking] = useState(false);
  const [revoking, setRevoking] = useState<RuntimeKey | null>(null);
  const revoke = useRevokeRuntimeKey();
  const [deleting, setDeleting] = useState<RuntimeKey | null>(null);
  const remove = useDeleteRuntimeKey();

  const newKey = (
    <Button variant="primary" icon="plus" onClick={() => setMaking(true)}>
      New API key
    </Button>
  );

  return (
    <>
      <PageHeader
        title={ada ? 'Runtime keys' : 'API Keys'}
        description="Your apps call your self-hosted runtime with an API key as the bearer. Each key is shown once, when you make it."
        actions={newKey}
      />

      {keys.isPending && <LoadingCard />}
      {keys.error && <ApiErrorNotice error={keys.error} />}
      {keys.data?.length === 0 && (
        <EmptyState icon="key" title="No API keys yet" action={newKey}>
          Make one for each app that calls your runtime, so you can revoke one without the others.
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
                meta={`${status.meta} · ${usage(key)}`}
                actions={
                  status.live ? (
                    <Button size="sm" variant="danger" onClick={() => setRevoking(key)}>
                      Revoke
                    </Button>
                  ) : (
                    <Button size="sm" variant="ghost" icon="trash" onClick={() => setDeleting(key)}>
                      Delete
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
        open={deleting !== null}
        title="Delete this API key?"
        description={
          <>
            <strong>{deleting?.name}</strong> already stopped working. Deleting it removes it from this list.
          </>
        }
        confirmLabel="Delete"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() => deleting && remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        onClose={() => {
          remove.reset();
          setDeleting(null);
        }}
      />

      <ConfirmDialog
        open={revoking !== null}
        title="Revoke this API key?"
        description={
          <>
            Apps using <strong>{revoking?.name}</strong> stop reaching your runtime at once. This cannot be undone.
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

/** Name a key and the self-hosted runtime it calls (the first, until another is chosen), then show it once. */
function NewKeyDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateRuntimeKey();
  const runtimes = useSelfRuntimes();
  const [name, setName] = useState('');
  const [picked, setPicked] = useState('');
  const [days, setDays] = useState('30');
  const [made, setMade] = useState<NewRuntimeKey | null>(null);
  const runtimeId = picked || runtimes.data?.[0]?.id || '';

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({ name: name.trim(), runtime_id: runtimeId, expires_in_days: days === 'never' ? null : Number(days) }, { onSuccess: setMade });
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
          <Button variant="primary" type="submit" form="new-key" loading={create.isPending} disabled={!name.trim() || !runtimeId}>
            Make key
          </Button>
        </>
      }
    >
      <form id="new-key" className={styles.form} onSubmit={submit}>
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Billing worker" autoFocus />
        {runtimes.data && runtimes.data.length > 0 && (
          <Select
            label="Runtime"
            hint="The self-hosted runtime it calls."
            value={runtimeId}
            onChange={(e) => setPicked(e.target.value)}
            options={runtimes.data.map((runtime) => ({ value: runtime.id, label: runtime.name }))}
          />
        )}
        {runtimes.data?.length === 0 && (
          <p className={styles.note}>
            A key calls a self-hosted runtime at its address. Add one on <Link to="/runtimes">Runtimes</Link> first.
          </p>
        )}
        <ApiErrorNotice error={runtimes.error} />
        <Select label="Expires after" value={days} onChange={(e) => setDays(e.target.value)} options={lifetimes} />
        {days === 'never' && (
          <ErrorNotice message="This key never expires. If it leaks, it works until you revoke it. Choose an expiry unless you must." />
        )}
        <ApiErrorNotice error={create.error} />
      </form>
    </Dialog>
  );
}
