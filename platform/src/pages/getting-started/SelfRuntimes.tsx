import { useState, type FormEvent } from 'react';
import { useDeleteSelfRuntime, useIssueOfflineLicence, useRotateSelfRuntimeToken, useSelfRuntimes } from '@/api/queries';
import type { OfflineLicence, SelfRuntime } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { List, Row } from '@/components/List';
import { ago, date } from '@/lib/format';
import { Button, Chip, CopyField, Dialog, TextField, type ChipTone } from '@/ui';
import { hostOf } from './snippets';
import styles from './GettingStarted.module.css';

const stateChip: Record<SelfRuntime['state'], { label: string; tone: ChipTone }> = {
  online: { label: 'Running', tone: 'green' },
  offline: { label: 'Offline', tone: 'amber' },
  pending: { label: 'Not seen yet', tone: 'neutral' },
};

function meta(runtime: SelfRuntime): string {
  const parts = [hostOf(runtime.public_url)];
  if (runtime.version) parts.push(runtime.version);
  parts.push(runtime.last_heartbeat_at ? `last heartbeat ${ago(runtime.last_heartbeat_at)}` : 'no heartbeat yet');
  return parts.join(' · ');
}

/** The runtimes registered to run elsewhere, with their token, licence and removal. */
export function SelfRuntimes() {
  const runtimes = useSelfRuntimes();
  const rotate = useRotateSelfRuntimeToken();
  const remove = useDeleteSelfRuntime();
  const [rotating, setRotating] = useState<SelfRuntime | null>(null);
  const [token, setToken] = useState<{ name: string; token: string } | null>(null);
  const [deleting, setDeleting] = useState<SelfRuntime | null>(null);
  const [licensing, setLicensing] = useState<SelfRuntime | null>(null);

  if (runtimes.error) return <ApiErrorNotice error={runtimes.error} />;
  if (!runtimes.data?.length) return null;

  return (
    <section className={styles.part} aria-labelledby="self-runtimes">
      <h2 id="self-runtimes" className={styles.subTitle}>
        Your self-hosted runtimes
      </h2>
      <List label="Self-hosted runtimes">
        {runtimes.data.map((runtime) => (
          <Row
            key={runtime.id}
            title={runtime.name}
            badges={
              <Chip tone={stateChip[runtime.state].tone} dot={runtime.state === 'online'}>
                {stateChip[runtime.state].label}
              </Chip>
            }
            meta={meta(runtime)}
            actions={
              <>
                <Button size="sm" variant="ghost" onClick={() => setLicensing(runtime)}>
                  Offline licence
                </Button>
                <Button size="sm" onClick={() => setRotating(runtime)}>
                  Rotate token
                </Button>
                <Button size="sm" variant="ghost" icon="trash" onClick={() => setDeleting(runtime)}>
                  Delete
                </Button>
              </>
            }
          />
        ))}
      </List>

      <ConfirmDialog
        open={rotating !== null}
        title="Rotate this runtime’s token?"
        description={
          <>
            <strong>{rotating?.name}</strong> stops reaching Glyphh with its old token at once. Set the new one where it runs.
          </>
        }
        confirmLabel="Rotate"
        pending={rotate.isPending}
        error={rotate.error}
        onConfirm={() =>
          rotating &&
          rotate.mutate(rotating.id, {
            onSuccess: (made) => {
              setToken({ name: rotating.name, token: made.token });
              setRotating(null);
            },
          })
        }
        onClose={() => {
          rotate.reset();
          setRotating(null);
        }}
      />

      <Dialog
        open={token !== null}
        onClose={() => setToken(null)}
        title="The new runtime token"
        description={`Copy it now and set it as RROTOR_RUNTIME_TOKEN for ${token?.name}. You won’t see it again.`}
        actions={
          <Button variant="primary" onClick={() => setToken(null)}>
            Done
          </Button>
        }
      >
        {token && <CopyField value={token.token} label="runtime token" />}
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete this runtime?"
        description={
          <>
            <strong>{deleting?.name}</strong> can no longer link to Glyphh or renew its licence. This cannot be undone.
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

      {licensing && <OfflineLicenceDialog runtime={licensing} onClose={() => setLicensing(null)} />}
    </section>
  );
}

/** For a runtime that cannot reach Glyphh: a licence it checks with no network at all. */
function OfflineLicenceDialog({ runtime, onClose }: { runtime: SelfRuntime; onClose: () => void }) {
  const issue = useIssueOfflineLicence();
  const [days, setDays] = useState('365');
  const [licence, setLicence] = useState<OfflineLicence | null>(null);
  const count = Number(days);
  const valid = Number.isInteger(count) && count >= 1 && count <= 365;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    issue.mutate({ id: runtime.id, days: count }, { onSuccess: setLicence });
  };

  if (licence) {
    return (
      <Dialog
        open
        onClose={onClose}
        title="The offline licence"
        description={`Set it as RROTOR_LICENCE for ${runtime.name}, or save it as /data/licence.token. It expires ${date(licence.expires_at)}.`}
        actions={
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        }
      >
        <CopyField value={licence.token} label="licence" />
      </Dialog>
    );
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title="Issue an offline licence"
      description={`For ${runtime.name} on a network with no way out. Run it with RROTOR_LINK=off and this licence.`}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="offline-licence" loading={issue.isPending} disabled={!valid}>
            Issue licence
          </Button>
        </>
      }
    >
      <form id="offline-licence" className={styles.form} onSubmit={submit}>
        <TextField
          label="Days"
          type="number"
          min={1}
          max={365}
          value={days}
          onChange={(e) => setDays(e.target.value)}
          hint="Up to 365. Issue a new one before it runs out."
          error={days && !valid ? 'From 1 to 365 days.' : undefined}
        />
        <ApiErrorNotice error={issue.error} />
      </form>
    </Dialog>
  );
}
