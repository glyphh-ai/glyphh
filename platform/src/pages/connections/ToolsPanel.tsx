import { useState } from 'react';
import type { Connection, ConnectionTool } from '@/api/bots';
import { readsOnly, useAppTools, useToolChoices, type ToolChoice } from '@/api/connections';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { cx } from '@/lib/cx';
import { EmptyState, Icon, Skeleton } from '@/ui';
import styles from './connections.module.css';

const CHOICES: Record<ToolChoice, string> = { allow: 'Allowed', block: 'Blocked' };

/** A small select of Allowed or Blocked; a group's shows Mixed while its tools differ. */
function Choice({ label, value, onChange }: { label: string; value: ToolChoice | 'mixed'; onChange: (c: ToolChoice) => void }) {
  return (
    <span className={cx(styles.choice, value === 'block' && styles.blocked)}>
      <Icon name={value === 'block' ? 'close' : 'check'} size={14} />
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value as ToolChoice)}>
        {value === 'mixed' && (
          <option value="mixed" disabled>
            Mixed
          </option>
        )}
        {(Object.keys(CHOICES) as ToolChoice[]).map((c) => (
          <option key={c} value={c}>
            {CHOICES[c]}
          </option>
        ))}
      </select>
      <Icon name="chevronDown" size={12} />
    </span>
  );
}

function Group({ title, tools, choices }: { title: string; tools: ConnectionTool[]; choices: ReturnType<typeof useToolChoices> }) {
  const [open, setOpen] = useState(true);
  if (tools.length === 0) return null;
  const all = new Set(tools.map((t) => choices.choiceOf(t.key)));
  const value = all.size === 1 ? [...all][0]! : 'mixed';
  return (
    <section className={styles.group} aria-label={title}>
      <div className={styles.groupHead}>
        <button type="button" className={styles.groupToggle} aria-expanded={open} onClick={() => setOpen(!open)}>
          {title} <span className={styles.muted}>{tools.length}</span>
          <Icon name={open ? 'chevronDown' : 'chevronRight'} size={14} />
        </button>
        <Choice label={`All ${title.toLowerCase()}`} value={value} onChange={(c) => choices.set(tools.map((t) => t.key), c)} />
      </div>
      {open && (
        <ul className={styles.tools}>
          {tools.map((t) => (
            <li key={t.key} className={styles.tool}>
              <span className={styles.toolName} title={t.key}>
                {t.name}
              </span>
              <span className={styles.toolAbout}>{t.description ?? t.key}</span>
              <Choice label={t.name} value={choices.choiceOf(t.key)} onChange={(c) => choices.set([t.key], c)} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** The app's tools, read-only ones apart from those that write, send or delete, each allowed or blocked for bots. */
export function ToolsPanel({ connection }: { connection: Connection }) {
  const tools = useAppTools(connection.id);
  const choices = useToolChoices(connection.id);
  const reads = (tools.data ?? []).filter(readsOnly);
  const writes = (tools.data ?? []).filter((t) => !readsOnly(t));

  return (
    <div className={styles.sections}>
      <p className={styles.lede}>
        Choose which of {connection.app_name}’s tools your bots may be given. For now the choice is kept in this browser; each bot still uses only the tools set on the bot itself.
      </p>
      <ApiErrorNotice error={tools.error} />
      {tools.isPending ? (
        <ul className={styles.tools} aria-busy="true" aria-label="Loading tools">
          {Array.from({ length: 6 }, (_, i) => (
            <li key={i} className={styles.tool} aria-hidden="true">
              <Skeleton height={14} width="60%" />
              <Skeleton height={12} width="90%" />
              <Skeleton height={14} width={90} />
            </li>
          ))}
        </ul>
      ) : tools.data?.length === 0 ? (
        <EmptyState icon="layers" title="No tools">
          Pipedream has no actions for {connection.app_name} yet.
        </EmptyState>
      ) : (
        <>
          <Group title="Read-only tools" tools={reads} choices={choices} />
          <Group title="Write/delete tools" tools={writes} choices={choices} />
        </>
      )}
    </div>
  );
}
