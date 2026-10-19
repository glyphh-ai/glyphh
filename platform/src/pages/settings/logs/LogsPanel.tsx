import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { keys, useLogs, type LogFilters } from '@/api/queries';
import type { LogRecord, RuntimeNode } from '@/api/types';
import { stamp } from '@/lib/format';
import { Button, Chip, EmptyState, LoadingCard, Select, TextField } from '@/ui';
import { anySet, FilterBar, WhereFilters } from './Filters';
import { Details, Live, Older, ReadError } from './Live';
import { NothingSent } from './NothingSent';
import { extraFields, levelBadge, levelOptions, runtimeName, sourceText } from './telemetry';
import styles from './Logs.module.css';

const shown = ['id', 'at', 'runtime_id', 'runtime', 'node_id', 'level', 'severity', 'body', 'attributes'] as const;

/** The runtimes' log records, newest first, filtered by runtime, node, level and above, time and words. */
export function LogsPanel({ nodes }: { nodes: RuntimeNode[] | undefined }) {
  const client = useQueryClient();
  const [filters, setFilters] = useState<LogFilters>({});
  const [words, setWords] = useState('');
  const logs = useLogs(filters);
  const records = logs.data?.pages.flatMap((page) => page.records ?? []) ?? [];

  const clear = () => {
    setFilters({});
    setWords('');
  };

  return (
    <>
      <FilterBar label="Filter log lines" onSearch={() => setFilters({ ...filters, text: words })}>
        <WhereFilters nodes={nodes} filters={filters} onChange={setFilters} />
        <Select label="Level" options={levelOptions} value={filters.level ?? ''} onChange={(e) => setFilters({ ...filters, level: e.target.value })} />
        <TextField label="Words" type="search" placeholder="In the message" value={words} onChange={(e) => setWords(e.target.value)} />
      </FilterBar>
      <Live />
      {logs.isPending && <LoadingCard />}
      <ReadError error={logs.error} onRestart={() => void client.resetQueries({ queryKey: keys.logs })} />
      {logs.data &&
        records.length === 0 &&
        (anySet(filters) ? (
          <EmptyState icon="logs" title="No log lines match" action={<Button onClick={clear}>Clear filters</Button>} />
        ) : (
          <NothingSent title="No log lines yet" />
        ))}
      {records.length > 0 && (
        <ol className={styles.lines} aria-label="Log lines">
          {records.map((record, i) => (
            <Line key={record.id ?? `${record.at}-${i}`} record={record} nodes={nodes} />
          ))}
        </ol>
      )}
      <Older more={logs.hasNextPage} loading={logs.isFetchingNextPage} onMore={() => void logs.fetchNextPage()} />
    </>
  );
}

function Line({ record, nodes }: { record: LogRecord; nodes: RuntimeNode[] | undefined }) {
  const level = levelBadge(record.level);
  const attributes = record.attributes && typeof record.attributes === 'object' ? record.attributes : {};
  return (
    <li className={styles.line}>
      <time className={styles.time} dateTime={record.at}>
        {stamp(record.at)}
      </time>
      <span className={styles.badge}>{level && <Chip tone={level.tone}>{level.label}</Chip>}</span>
      <div className={styles.body}>
        <p className={styles.message}>{record.body ?? ''}</p>
        <p className={styles.source}>{sourceText(runtimeName(record.runtime_id, record.runtime, nodes), record.node_id)}</p>
        <Details fields={{ ...attributes, ...extraFields(record, shown) }} />
      </div>
    </li>
  );
}
