import { useState } from 'react';
import { useLogs, type LogFilters } from '@/api/queries';
import type { LogLine, RuntimeNode } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { stamp } from '@/lib/format';
import { Button, Chip, EmptyState, LoadingCard, Select, TextField } from '@/ui';
import { anySet, FilterBar, WhereFilters } from './Filters';
import { Details, Live, Older } from './Live';
import { NothingSent } from './NothingSent';
import { extraFields, levelBadge, levelOptions, runtimeName, sourceText } from './telemetry';
import styles from './Logs.module.css';

const shown = ['at', 'runtime_id', 'runtime', 'node_id', 'level', 'message', 'attributes'] as const;

/** The runtimes' log lines, newest first, filtered by runtime, node, level, time and words. */
export function LogsPanel({ nodes }: { nodes: RuntimeNode[] | undefined }) {
  const [filters, setFilters] = useState<LogFilters>({});
  const [words, setWords] = useState('');
  const logs = useLogs(filters);
  const lines = logs.data?.pages.flatMap((page) => page.logs ?? []) ?? [];

  const clear = () => {
    setFilters({});
    setWords('');
  };

  return (
    <>
      <FilterBar label="Filter log lines" onSearch={() => setFilters({ ...filters, q: words })}>
        <WhereFilters nodes={nodes} filters={filters} onChange={setFilters} />
        <Select label="Level" options={levelOptions} value={filters.level ?? ''} onChange={(e) => setFilters({ ...filters, level: e.target.value })} />
        <TextField label="Words" type="search" placeholder="In the message" value={words} onChange={(e) => setWords(e.target.value)} />
      </FilterBar>
      <Live />
      {logs.isPending && <LoadingCard />}
      <ApiErrorNotice error={logs.error} />
      {logs.data &&
        lines.length === 0 &&
        (anySet(filters) ? (
          <EmptyState icon="logs" title="No log lines match" action={<Button onClick={clear}>Clear filters</Button>} />
        ) : (
          <NothingSent title="No log lines yet" />
        ))}
      {lines.length > 0 && (
        <ol className={styles.lines} aria-label="Log lines">
          {lines.map((line, i) => (
            <Line key={`${line.at}-${i}`} line={line} nodes={nodes} />
          ))}
        </ol>
      )}
      <Older more={logs.hasNextPage} loading={logs.isFetchingNextPage} onMore={() => void logs.fetchNextPage()} />
    </>
  );
}

function Line({ line, nodes }: { line: LogLine; nodes: RuntimeNode[] | undefined }) {
  const level = levelBadge(line.level);
  const attributes = line.attributes && typeof line.attributes === 'object' ? line.attributes : {};
  return (
    <li className={styles.line}>
      <time className={styles.time} dateTime={line.at}>
        {stamp(line.at)}
      </time>
      <span className={styles.badge}>{level && <Chip tone={level.tone}>{level.label}</Chip>}</span>
      <div className={styles.body}>
        <p className={styles.message}>{line.message ?? ''}</p>
        <p className={styles.source}>{sourceText(runtimeName(line.runtime_id, line.runtime, nodes), line.node_id)}</p>
        <Details fields={{ ...attributes, ...extraFields(line, shown) }} />
      </div>
    </li>
  );
}
