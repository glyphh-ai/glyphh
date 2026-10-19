import type { FormEvent, ReactNode } from 'react';
import type { RuntimeNode } from '@/api/types';
import { Button, Select } from '@/ui';
import { nodeOptions, runtimeOptions, sinceOptions } from './telemetry';
import styles from './Logs.module.css';

type Where = { runtime?: string; node?: string; since?: string };

/** The runtime, node and window filters every tab shares; a new runtime clears the node. */
export function WhereFilters<T extends Where>({ nodes, filters, onChange }: { nodes: RuntimeNode[] | undefined; filters: T; onChange: (next: T) => void }) {
  const runtime = filters.runtime ?? '';
  const nodeChoices = nodeOptions(nodes, runtime);
  return (
    <>
      <Select label="Runtime" options={runtimeOptions(nodes)} value={runtime} onChange={(e) => onChange({ ...filters, runtime: e.target.value, node: '' })} />
      {nodeChoices.length > 1 && (
        <Select label="Node" options={nodeChoices} value={filters.node ?? ''} onChange={(e) => onChange({ ...filters, node: e.target.value })} />
      )}
      <Select label="Time" options={sinceOptions} value={filters.since ?? ''} onChange={(e) => onChange({ ...filters, since: e.target.value })} />
    </>
  );
}

/**
 * A row of filters: the selects apply at once; the text fields when the person searches, so a half-typed word does
 * not read the server at every key.
 */
export function FilterBar({ label, children, onSearch }: { label: string; children: ReactNode; onSearch: () => void }) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSearch();
  }
  return (
    <form className={styles.filters} aria-label={label} onSubmit={submit}>
      {children}
      <Button type="submit" icon="search" className={styles.search}>
        Search
      </Button>
    </form>
  );
}

/** Whether any filter is set, so an empty list can say "none match" rather than "nothing sent". */
export const anySet = (filters: Record<string, string | undefined>) => Object.values(filters).some((value) => value?.trim());
