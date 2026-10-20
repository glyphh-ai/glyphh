import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import { keys, useAudit, type AuditFilters } from '@/api/queries';
import type { AuditEvent, RuntimeNode } from '@/api/types';
import { stamp } from '@/lib/format';
import { Button, Chip, EmptyState, LoadingCard, TextField } from '@/ui';
import { anySet, FilterBar, WhereFilters } from './Filters';
import { Details, Live, Older, ReadError } from './Live';
import { NothingSent } from './NothingSent';
import { actorText, auditShown, extraFields, outcomeBadge, runtimeName, sourceText } from './telemetry';
import styles from './Logs.module.css';

const shown = ['id', 'at', 'runtime_id', 'runtime', 'node_id', 'kind', 'attributes'] as const;

/** Who did what on the runtimes and how it ended, newest first: recorded by rrotor on Enterprise. */
export function AuditPanel({ nodes }: { nodes: RuntimeNode[] | undefined }) {
  const client = useQueryClient();
  const [filters, setFilters] = useState<AuditFilters>({});
  const [kind, setKind] = useState('');
  const audit = useAudit(filters);
  const events = audit.data?.pages.flatMap((page) => page.events ?? []) ?? [];

  const clear = () => {
    setFilters({});
    setKind('');
  };

  return (
    <>
      <p className={styles.note} role="note">
        rrotor records audit events on Enterprise. Below Enterprise it sends them as log lines instead: see <Link to="/logs">Logs</Link>.
      </p>
      <FilterBar label="Filter audit events" onSearch={() => setFilters({ ...filters, kind })}>
        <WhereFilters nodes={nodes} filters={filters} onChange={setFilters} />
        <TextField label="Kind" type="search" placeholder="Such as run.call" value={kind} onChange={(e) => setKind(e.target.value)} />
      </FilterBar>
      <Live />
      {audit.isPending && <LoadingCard />}
      <ReadError error={audit.error} onRestart={() => void client.resetQueries({ queryKey: keys.audit })} />
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
            <Event key={event.id ?? `${event.at}-${i}`} event={event} nodes={nodes} />
          ))}
        </ol>
      )}
      <Older more={audit.hasNextPage} loading={audit.isFetchingNextPage} onMore={() => void audit.fetchNextPage()} />
    </>
  );
}

function Event({ event, nodes }: { event: AuditEvent; nodes: RuntimeNode[] | undefined }) {
  const attributes = event.attributes && typeof event.attributes === 'object' ? event.attributes : {};
  const outcome = outcomeBadge(attributes);
  const via = typeof attributes.via === 'string' ? attributes.via : null;
  const meta = [`By ${actorText(attributes)}`];
  if (via) meta.push(`via ${via}`);
  meta.push(sourceText(runtimeName(event.runtime_id, event.runtime, nodes), event.node_id));
  return (
    <li className={styles.line}>
      <time className={styles.time} dateTime={event.at}>
        {stamp(event.at)}
      </time>
      <span className={styles.badge}>{outcome && <Chip tone={outcome.tone}>{outcome.label}</Chip>}</span>
      <div className={styles.body}>
        <p className={styles.message}>{event.kind ?? 'An event'}</p>
        <p className={styles.source}>{meta.join(' · ')}</p>
        <Details fields={{ ...extraFields(attributes, auditShown), ...extraFields(event, shown) }} />
      </div>
    </li>
  );
}
