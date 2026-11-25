import { useState } from 'react';
import { useAckEvent, useAckEvents, useAdminEvents, type EventFilter, type OpsEvent } from '@/api/admin';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { stamp } from '@/lib/format';
import { Button, Card, Chip, EmptyState, LoadingCard, Select, Switch, TextField, useToast } from '@/ui';
import { n } from '../parts';
import styles from '../admin.module.css';

const severities = [
  { value: '', label: 'Any severity' },
  { value: 'critical', label: 'Critical' },
  { value: 'error', label: 'Error' },
  { value: 'warning', label: 'Warning' },
];

const tones = { critical: 'red', error: 'red', warning: 'amber' } as const;

/**
 * The server's own errors and warnings: crashes, 5xx, workers, the tick, Stripe, jobs. Alike ones within a minute are
 * one row with their count. Acknowledged once someone has looked; open errors of the last hour raise an alert.
 */
export function EventsPage() {
  const toast = useToast();
  const [filter, setFilter] = useState<EventFilter>({ open_only: true });
  const events = useAdminEvents(filter);
  const ackAll = useAckEvents();
  const set = (change: Partial<EventFilter>) => setFilter((f) => ({ ...f, ...change, before: undefined }));
  const acknowledgeAll = () =>
    ackAll.mutate(
      { severity: filter.severity || undefined, kind: filter.kind || undefined },
      { onSuccess: (done) => toast.show(`${n(done.acknowledged)} acknowledged.`) },
    );

  return (
    <div className={styles.page}>
      <PageHeader
        title="Log alerts"
        description="The server’s errors and warnings, from the API, the Ada workers, the minute tick, Stripe and jobs."
        actions={
          <Button loading={ackAll.isPending} onClick={acknowledgeAll}>
            Acknowledge all shown
          </Button>
        }
      />
      <div className={styles.filters}>
        <Select label="Severity" value={filter.severity ?? ''} options={severities} onChange={(e) => set({ severity: e.target.value || undefined })} />
        <TextField label="Kind" placeholder="crash, http, worker, tick, stripe, job, staff" value={filter.kind ?? ''} onChange={(e) => set({ kind: e.target.value || undefined })} />
        <div className={styles.switchRow}>
          <Switch label="Open only" checked={Boolean(filter.open_only)} onChange={(on) => set({ open_only: on })} />
          <span aria-hidden="true">Open only</span>
        </div>
      </div>
      <ApiErrorNotice error={ackAll.error} />
      {events.isPending && <LoadingCard />}
      <ApiErrorNotice error={events.error} />
      {events.data?.events.length === 0 && <EmptyState icon="check" title="Nothing here" />}
      {events.data && events.data.events.length > 0 && (
        <Card>
          <div className={styles.tableBox}>
            <table className={styles.table} aria-label="Events">
              <thead>
                <tr>
                  <th>Last seen</th>
                  <th>Severity</th>
                  <th>Kind</th>
                  <th>What</th>
                  <th className={styles.num}>Times</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {events.data.events.map((e) => (
                  <EventRow key={e.id} event={e} />
                ))}
              </tbody>
            </table>
          </div>
          {events.data.next_before && (
            <div className={styles.pager}>
              <span />
              <Button size="sm" onClick={() => setFilter((f) => ({ ...f, before: events.data!.next_before! }))}>
                Older
              </Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function EventRow({ event }: { event: OpsEvent }) {
  const ack = useAckEvent();
  return (
    <tr>
      <td className={styles.num}>{stamp(event.last_at)}</td>
      <td>
        <Chip tone={tones[event.severity]}>{event.severity}</Chip>
      </td>
      <td>{event.kind}</td>
      <td>
        <div>{event.message}</div>
        <details>
          <summary className={styles.meta}>{`${event.source}${event.org_id ? `, org ${event.org_id}` : ''}${event.trace_id ? `, trace ${event.trace_id}` : ''}`}</summary>
          <pre className={styles.detail}>{JSON.stringify(event.detail, null, 2)}</pre>
        </details>
      </td>
      <td className={styles.num}>{n(event.count)}</td>
      <td>
        {event.acknowledged_at ? (
          <span className={styles.meta}>{`Seen by ${event.acknowledged_by ?? 'staff'}`}</span>
        ) : (
          <Button size="sm" loading={ack.isPending} onClick={() => ack.mutate(event.id)}>
            Acknowledge
          </Button>
        )}
      </td>
    </tr>
  );
}
