import { useState } from 'react';
import { useSetPermissions, type Connection, type ConnectionTool, type Permission } from '@/api/bots';
import { PERMISSIONS, readsOnly, useAppTools } from '@/api/connections';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { cx } from '@/lib/cx';
import { EmptyState, Icon, Skeleton, type IconName } from '@/ui';
import styles from './connections.module.css';

const MODES = Object.keys(PERMISSIONS) as Permission[];
const ICONS: Record<Permission, IconName> = { allow: 'check', ask: 'alert', deny: 'close' };
const TONES: Record<Permission, string | undefined> = { allow: styles.allowed, ask: styles.asks, deny: styles.blocked };

/** A small select of Always allow, Needs approval or Blocked; a group's shows Mixed while its tools differ. */
function Choice({
  label,
  value,
  busy,
  onChange,
}: {
  label: string;
  value: Permission | 'mixed';
  busy: boolean;
  onChange: (p: Permission) => void;
}) {
  return (
    <span className={cx(styles.choice, value !== 'mixed' && TONES[value])} aria-busy={busy || undefined}>
      <Icon name={value === 'mixed' ? 'layers' : ICONS[value]} size={14} />
      <select aria-label={label} value={value} disabled={busy} onChange={(e) => onChange(e.target.value as Permission)}>
        {value === 'mixed' && (
          <option value="mixed" disabled>
            Mixed
          </option>
        )}
        {MODES.map((p) => (
          <option key={p} value={p}>
            {PERMISSIONS[p]}
          </option>
        ))}
      </select>
      <Icon name="chevronDown" size={12} />
    </span>
  );
}

type SetFn = (keys: string[], p: Permission) => void;

function Group({ title, tools, set, busy }: { title: string; tools: ConnectionTool[]; set: SetFn; busy: boolean }) {
  const [open, setOpen] = useState(true);
  if (tools.length === 0) return null;
  const all = new Set(tools.map((t) => t.permission));
  const value = all.size === 1 ? [...all][0]! : 'mixed';
  return (
    <section className={styles.group} aria-label={title}>
      <div className={styles.groupHead}>
        <button type="button" className={styles.groupToggle} aria-expanded={open} onClick={() => setOpen(!open)}>
          {title} <span className={styles.muted}>{tools.length}</span>
          <Icon name={open ? 'chevronDown' : 'chevronRight'} size={14} />
        </button>
        <Choice label={`All ${title.toLowerCase()}`} value={value} busy={busy} onChange={(p) => set(tools.map((t) => t.key), p)} />
      </div>
      {open && (
        <ul className={styles.tools}>
          {tools.map((t) => (
            <li key={t.key} className={styles.tool}>
              <span className={styles.toolName} title={t.key}>
                {t.name}
              </span>
              <span className={styles.toolAbout}>{t.description || t.key}</span>
              <Choice label={t.name} value={t.permission} busy={busy} onChange={(p) => set([t.key], p)} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * The app's tools, read-only ones apart from those that write, send or delete, each one always allowed, waiting for
 * the person's approval (a tool never set) or blocked for every bot of the org; kept on the server.
 */
export function ToolsPanel({ connection }: { connection: Connection }) {
  const tools = useAppTools(connection.id);
  const save = useSetPermissions(connection.id);
  const set: SetFn = (keys, p) => save.mutate(Object.fromEntries(keys.map((k) => [k, p])));
  const reads = (tools.data ?? []).filter(readsOnly);
  const writes = (tools.data ?? []).filter((t) => !readsOnly(t));

  return (
    <div className={styles.sections}>
      <p className={styles.lede}>
        Choose what your bots may do with each of {connection.app_name}’s tools: always allow it, have a bot wait for your approval in
        Approvals, or block it. A tool you never set needs approval.
      </p>
      <ApiErrorNotice error={tools.error ?? save.error} />
      {tools.isPending ? (
        <ul className={styles.tools} aria-busy="true" aria-label="Loading tools">
          {Array.from({ length: 6 }, (_, i) => (
            <li key={i} className={styles.tool} aria-hidden="true">
              <Skeleton height={14} width="60%" />
              <Skeleton height={12} width="90%" />
              <Skeleton height={14} width={120} />
            </li>
          ))}
        </ul>
      ) : tools.data?.length === 0 ? (
        <EmptyState icon="layers" title="No tools">
          Pipedream has no actions for {connection.app_name} yet.
        </EmptyState>
      ) : (
        <>
          <Group title="Read-only tools" tools={reads} set={set} busy={save.isPending} />
          <Group title="Write/delete tools" tools={writes} set={set} busy={save.isPending} />
        </>
      )}
    </div>
  );
}
