import { useState } from 'react';
import { Link } from 'react-router';
import { useAudit, type AuditFilters } from '@/api/queries';
import type { AuditEvent, RuntimeNode } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { stamp } from '@/lib/format';
import { Button, Chip, EmptyState, LoadingCard, TextField } from '@/ui';
import { anySet, FilterBar, WhereFilters } from './Filters';
import { Details, Live, Older } from './Live';
import { NothingSent } from './NothingSent';
import { actorText, extraFields, outcomeBadge, runtimeName, sourceText, targetText } from './telemetry';
import styles from './Logs.module.css';

const shown = ['at', 'runtime_id', 'runtime', 'node_id', 'actor', 'action', 'target', 'outcome', 'via'] as const;

/** Who did what on the runtimes, newest first: recorded by rrotor on Enterprise. */
export function AuditPanel({ nodes }: { nodes: RuntimeNode[] | undefined }) {
  const [filters, setFilters] = useState<AuditFilters>({});
  const [typed, setTyped] = useState({ actor: '', action: '' });
  const audit = useAudit(filters);
  const events = audit.data?.pages.flatMap((page) => page.events ?? []) ?? [];

  const clear = () => {
    setFilters({});
    setTyped({ actor: '', action: '' });
  };

  return (
    <>
      <p className={styles.note} role="note">
        rrotor records audit events on Enterprise. Below Enterprise it sends them as log lines instead: see <Link to="/settings/logs">Logs</Link>.
      </p>
      <FilterBar label="Filter audit events" onSearch={() => setFilters({ ...filters, ...typed })}>
        <WhereFilters nodes={nodes} filters={filters} onChange={setFilters} />
        <TextField label="Who" type="search" placeholder="A member or key" value={typed.actor} onChange={(e) => setTyped({ ...typed, actor: e.target.value })} />
        <TextField label="Action" type="search" placeholder="Such as model.delete" value={typed.action} onChange={(e) => setTyped({ ...typed, action: e.target.value })} />
      </FilterBar>
      <Live />
      {audit.isPending && <LoadingCard />}
      <ApiErrorNotice error={audit.error} />
      {audit.data &&
        events.length === 0 &&
        (anySet(filters) ? (
          <EmptyState icon="logs" title="No audit events match" action={<Button onClick={clear}>Clear filters</Button>} />
        ) : (
          <NothingSent title="No audit events yet" />
        ))}
      {events.length > 0 && (
        <ol className={styles.lines} aria-label="Audit events">
          {events.map((event, i) => (
            <Event key={`${event.at}-${i}`} event={event} nodes={nodes} />
          ))}
        </ol>
      )}
      <Older more={audit.hasNextPage} loading={audit.isFetchingNextPage} onMore={() => void audit.fetchNextPage()} />
    </>
  );
}

function Event({ event, nodes }: { event: AuditEvent; nodes: RuntimeNode[] | undefined }) {
  const outcome = outcomeBadge(event.outcome);
  const target = targetText(event.target);
  const meta = [`By ${actorText(event.actor)}`];
  if (event.via) meta.push(`via ${event.via}`);
  meta.push(sourceText(runtimeName(event.runtime_id, typeof event.runtime === 'string' ? event.runtime : null, nodes), event.node_id));
  return (
    <li className={styles.line}>
      <time className={styles.time} dateTime={event.at}>
        {stamp(event.at)}
      </time>
      <span className={styles.badge}>{outcome && <Chip tone={outcome.tone}>{outcome.label}</Chip>}</span>
      <div className={styles.body}>
        <p className={styles.message}>
          {event.action ?? 'An action'}
          {target && <span className={styles.target}> on {target}</span>}
        </p>
        <p className={styles.source}>{meta.join(' · ')}</p>
        <Details fields={extraFields(event, shown)} />
      </div>
    </li>
  );
}
