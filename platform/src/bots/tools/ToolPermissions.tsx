import { useMemo, useState } from 'react';
import type { ConnectionTool } from '@/api/bots';
import { toolKind, type ToolKind } from '@/api/connections';
import { cx } from '@/lib/cx';
import { Icon, Switch, TextField } from '@/ui';
import styles from './ToolPermissions.module.css';

const SECTIONS: { kind: ToolKind; title: string }[] = [
  { kind: 'read', title: 'Read-only tools' },
  { kind: 'write', title: 'Write/delete tools' },
];

type Props = {
  /** Names the list for a screen reader, e.g. "Gmail tools". */
  label: string;
  tools: ConnectionTool[];
  /** Whether the tool is on: off is a tool the bot never uses. */
  isOn: (tool: ConnectionTool) => boolean;
  onSwitch: (keys: string[], on: boolean) => void;
  /** Ask (needs approval) or allow: kept on the connection for every bot of the org. */
  onApproval: (keys: string[], ask: boolean) => void;
  busy?: boolean;
};

/** Needs approval (the raised hand) or always allowed (the tick), as a small button; mixed for a section that differs. */
function ApprovalButton({
  label,
  state,
  disabled,
  onClick,
}: {
  label: string;
  state: 'ask' | 'allow' | 'mixed';
  disabled: boolean;
  onClick: () => void;
}) {
  const words = state === 'ask' ? 'Needs approval' : state === 'allow' ? 'Always allowed' : 'Some need approval';
  return (
    <button
      type="button"
      className={cx(styles.approval, state === 'ask' && styles.asks, state === 'mixed' && styles.mixed)}
      aria-label={`Approval for ${label}`}
      aria-pressed={state === 'mixed' ? 'mixed' : state === 'ask'}
      title={disabled ? 'Off: never used' : `${words}. Click for ${state === 'ask' ? 'always allowed' : 'needs approval'}.`}
      disabled={disabled}
      onClick={onClick}
    >
      <Icon name={state === 'allow' ? 'check' : 'hand'} size={14} />
    </button>
  );
}

function Section({
  title,
  tools,
  open,
  onOpen,
  isOn,
  onSwitch,
  onApproval,
  busy,
}: Omit<Props, 'label' | 'tools'> & { title: string; tools: ConnectionTool[]; open: boolean; onOpen: () => void }) {
  const on = tools.filter(isOn);
  const asks = on.filter((t) => t.permission === 'ask').length;
  const approval = on.length === 0 || asks === on.length ? 'ask' : asks === 0 ? 'allow' : 'mixed';
  const allOn = on.length === tools.length;
  const lower = title.toLowerCase();

  return (
    <section className={styles.section} aria-label={title}>
      <div className={styles.head}>
        <button type="button" className={styles.toggle} aria-expanded={open} onClick={onOpen}>
          <Icon name={open ? 'chevronDown' : 'chevronRight'} size={14} />
          <span className={styles.title}>{title}</span>
          <span className={styles.count}>
            {on.length === tools.length ? tools.length : `${on.length}/${tools.length}`}
          </span>
        </button>
        <span className={styles.controls}>
          <ApprovalButton
            label={`all ${lower}`}
            state={approval}
            disabled={busy || on.length === 0}
            onClick={() => onApproval(on.map((t) => t.key), approval !== 'ask')}
          />
          <Switch label={`All ${lower}`} checked={allOn} disabled={busy} onChange={() => onSwitch(tools.map((t) => t.key), !allOn)} />
        </span>
      </div>
      {open && (
        <ul className={styles.rows}>
          {tools.map((t) => {
            const lit = isOn(t);
            return (
              <li key={t.key} className={cx(styles.row, !lit && styles.off)}>
                <span className={styles.name} title={t.description || t.key}>
                  {t.name}
                </span>
                <span className={styles.controls}>
                  <ApprovalButton
                    label={t.name}
                    state={t.permission === 'allow' ? 'allow' : 'ask'}
                    disabled={busy || !lit}
                    onClick={() => onApproval([t.key], t.permission === 'allow')}
                  />
                  <Switch label={t.name} checked={lit} disabled={busy} onChange={(next) => onSwitch([t.key], next)} />
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/**
 * A connection's tools as claude.ai's connector shows its tool permissions: read-only apart from those that write,
 * send or delete, each section folding away with its count, one line per tool (its description on hover), a switch
 * that is on unless the tool is never to be used, and a small hand for one that waits for the person's approval.
 * Search finds tools across the sections and opens the ones it finds them in.
 */
export function ToolPermissions({ label, tools, isOn, onSwitch, onApproval, busy = false }: Props) {
  const [q, setQ] = useState('');
  const [opened, setOpened] = useState<Partial<Record<ToolKind, boolean>>>({});
  const words = q.trim().toLowerCase();
  const shown = useMemo(
    () => tools.filter((t) => !words || `${t.name} ${t.key} ${t.description ?? ''}`.toLowerCase().includes(words)),
    [tools, words],
  );
  const sections = SECTIONS.map((s) => ({ ...s, tools: shown.filter((t) => toolKind(t) === s.kind) })).filter((s) => s.tools.length > 0);

  return (
    <div className={styles.root} role="group" aria-label={label}>
      <TextField label="Search tools" type="search" value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpened({}); // a new search opens every section it finds tools in
        }}
      />
      {sections.length === 0 ? (
        <p className={styles.none}>No tool matches “{q.trim()}”.</p>
      ) : (
        sections.map((s) => (
          <Section
            key={s.kind}
            title={s.title}
            tools={s.tools}
            open={opened[s.kind] ?? Boolean(words)}
            onOpen={() => setOpened((o) => ({ ...o, [s.kind]: !(o[s.kind] ?? Boolean(words)) }))}
            isOn={isOn}
            onSwitch={onSwitch}
            onApproval={onApproval}
            busy={busy}
          />
        ))
      )}
    </div>
  );
}
