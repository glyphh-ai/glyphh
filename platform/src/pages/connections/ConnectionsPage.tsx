import { useState } from 'react';
import { connectionsOff, useConnections, useRemoveConnection, type Connection } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard, useToast } from '@/ui';
import { AddConnectionDialog } from './AddConnectionDialog';
import styles from '../bots/bots.module.css';

/** The org's connections: the apps it has signed in to, for its bots to use with the tools each bot is given. */
export function ConnectionsPage() {
  const toast = useToast();
  const connections = useConnections();
  const remove = useRemoveConnection();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Connection | null>(null);
  const off = connectionsOff(connections.error);
  const add = (
    <Button variant="primary" icon="plus" onClick={() => setAdding(true)} disabled={off}>
      Add connection
    </Button>
  );

  return (
    <>
      <PageHeader title="Connections" description="Apps your organisation has connected. Each bot is given only the tools you choose from them." actions={add} />
      {connections.isPending && <LoadingCard />}
      {off ? (
        <EmptyState icon="external" title="Connections are not set up">
          The server has no Pipedream project yet, so no app can be connected.
        </EmptyState>
      ) : (
        <ApiErrorNotice error={connections.error} />
      )}
      {connections.data?.length === 0 && (
        <EmptyState icon="external" title="No connections yet" action={add}>
          Connect an app, such as Gmail or Slack, for your bots to use.
        </EmptyState>
      )}
      {connections.data && connections.data.length > 0 && (
        <Card>
          <ul className={styles.list} aria-label="Connections">
            {connections.data.map((c) => (
              <li key={c.id} className={styles.item}>
                {c.app_icon ? <img src={c.app_icon} alt="" className={styles.icon} /> : <span className={styles.icon} />}
                <div className={styles.grow}>
                  <div className={styles.toolName}>{c.app_name}</div>
                  <div className={styles.muted}>
                    {c.label ? `${c.label} · ` : ''}Connected {date(c.created_at)}
                  </div>
                </div>
                <Button variant="ghost" size="sm" icon="trash" onClick={() => setRemoving(c)} aria-label={`Remove ${c.app_name}`}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <AddConnectionDialog open={adding} onClose={() => setAdding(false)} />
      <ConfirmDialog
        open={removing !== null}
        title={`Remove ${removing?.app_name ?? 'this connection'}?`}
        description="Bots that use it lose its tools. You can connect the app again later."
        confirmLabel="Remove"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          removing &&
          remove.mutate(removing.id, {
            onSuccess: () => {
              toast.show(`${removing.app_name} is removed.`);
              setRemoving(null);
            },
          })
        }
        onClose={() => {
          remove.reset();
          setRemoving(null);
        }}
      />
    </>
  );
}
