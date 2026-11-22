import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { connectionsOff, useConnections, useConnectionTools, useScopeBot, type Bot, type Connection } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PERMISSIONS } from '@/api/connections';
import { plural } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard, Select, TextField, useToast } from '@/ui';
import { InClaude } from './ada';
import styles from './bots.module.css';
import look from './look.module.css';

type Scope = { connection_id: string; tools: string[] };

/** One connection on the bot: its tools as checkboxes, with search and all or none. */
function ConnectionScope({
  scope,
  connection,
  appName,
  onChange,
  onRemove,
}: {
  scope: Scope;
  connection: Connection | undefined;
  appName: string;
  onChange: (tools: string[]) => void;
  onRemove: () => void;
}) {
  const tools = useConnectionTools(scope.connection_id);
  const [q, setQ] = useState('');
  const chosen = new Set(scope.tools);
  const shown = useMemo(() => {
    const words = q.trim().toLowerCase();
    return (tools.data ?? []).filter((t) => !words || `${t.name} ${t.key} ${t.description ?? ''}`.toLowerCase().includes(words));
  }, [tools.data, q]);
  const title = connection?.label ? `${appName} · ${connection.label}` : appName;

  const toggle = (key: string) => onChange(chosen.has(key) ? scope.tools.filter((k) => k !== key) : [...scope.tools, key]);
  const all = () => onChange([...new Set([...scope.tools, ...shown.map((t) => t.key)])]);
  const none = () => {
    const hidden = new Set(shown.map((t) => t.key));
    onChange(scope.tools.filter((k) => !hidden.has(k)));
  };

  return (
    <Card>
      <section className={styles.form} aria-label={title}>
        <div className={styles.spread}>
          <div className={styles.row}>
            {connection?.app_icon && <img src={connection.app_icon} alt="" className={styles.icon} />}
            <div>
              <h2 className={styles.name}>{title}</h2>
              <span className={styles.muted}>
                {tools.data ? `${scope.tools.length} of ${plural(tools.data.length, 'tool')} allowed` : `${plural(scope.tools.length, 'tool')} allowed`}
              </span>
            </div>
          </div>
          <Button variant="ghost" size="sm" icon="trash" onClick={onRemove}>
            Take off
          </Button>
        </div>
        {tools.isPending && <LoadingCard />}
        <ApiErrorNotice error={tools.error} />
        {tools.data && tools.data.length > 0 && (
          <>
            <div className={styles.row}>
              <div className={styles.grow}>
                <TextField label="Search tools" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <Button variant="secondary" size="sm" onClick={all} disabled={shown.length === 0}>
                Select all
              </Button>
              <Button variant="secondary" size="sm" onClick={none} disabled={shown.length === 0}>
                Select none
              </Button>
            </div>
            {shown.length === 0 ? (
              <p className={styles.muted}>No tool matches “{q.trim()}”.</p>
            ) : (
              <ul className={styles.tools} aria-label={`${title} tools`}>
                {shown.map((t) => (
                  <li key={t.key}>
                    <label className={styles.tool}>
                      <input type="checkbox" checked={chosen.has(t.key)} onChange={() => toggle(t.key)} />
                      <span>
                        <span className={styles.toolName}>{t.name}</span>{' '}
                        {t.permission !== 'allow' && (
                          <span className={`${look.pill} ${look.pillSmall} ${t.permission === 'deny' ? '' : look.pillOn}`}>{PERMISSIONS[t.permission]}</span>
                        )}
                        {t.description && <span className={`${styles.muted} ${styles.block}`}>{t.description}</span>}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        {tools.data?.length === 0 && <p className={styles.muted}>This app has no tools.</p>}
        {connection && (
          <p className={styles.muted}>
            A tool that needs approval makes the bot wait for you in Approvals; a blocked one it never uses.{' '}
            <Link to={`/connections/${encodeURIComponent(connection.app)}?tab=tools`}>Change {appName}’s permissions</Link>
          </p>
        )}
      </section>
    </Card>
  );
}

/**
 * The tools the bot may use, per connection: add one of the org's connections, then tick the tools it may call.
 * A tool not ticked is one the bot never sees; one ticked still keeps the org's permission for it (needs approval or
 * blocked), shown beside it.
 */
export function ToolsTab({ bot }: { bot: Bot }) {
  const toast = useToast();
  const connections = useConnections();
  const scopeBot = useScopeBot(bot.slug);
  const [scopes, setScopes] = useState<Scope[]>(() => bot.connections.map((c) => ({ connection_id: c.connection_id, tools: [...c.tools] })));
  const [adding, setAdding] = useState('');
  const names = new Map(bot.connections.map((c) => [c.connection_id, c.app_name]));
  const byId = new Map((connections.data ?? []).map((c) => [c.id, c]));
  const free = (connections.data ?? []).filter((c) => !scopes.some((s) => s.connection_id === c.id));
  const pick = adding || free[0]?.id || '';

  const set = (id: string, tools: string[]) => setScopes((all) => all.map((s) => (s.connection_id === id ? { ...s, tools } : s)));
  const add = () => {
    if (!pick) return;
    setScopes((all) => [...all, { connection_id: pick, tools: [] }]);
    setAdding('');
  };
  const save = () => scopeBot.mutate(scopes, { onSuccess: () => toast.show(`${bot.name}’s tools are saved.`) });

  if (connectionsOff(connections.error)) {
    return <EmptyState icon="external" title="Connections are not set up">The server has no Pipedream project yet, so a bot can use no apps.</EmptyState>;
  }

  return (
    <div className={styles.stack}>
      <section className={look.section} aria-label="In Claude">
        <div className={look.labelRow}>
          <h2 className={look.label}>In Claude · the tools your Glyphh connection gives it</h2>
        </div>
        <div className={look.panel}>
          <InClaude bot={bot} />
        </div>
      </section>
      <div className={look.labelRow}>
        <h2 className={look.label}>Tools it may use · per connection</h2>
      </div>
      <ApiErrorNotice error={connections.error} />
      {connections.data?.length === 0 && scopes.length === 0 && (
        <EmptyState icon="external" title="No connections yet">
          <Link to="/connections">Connect an app</Link> first, then give the bot its tools here.
        </EmptyState>
      )}
      {free.length > 0 && (
        <div className={styles.row}>
          <div className={styles.grow}>
            <Select
              label="Add a connection"
              value={pick}
              onChange={(e) => setAdding(e.target.value)}
              options={free.map((c) => ({ value: c.id, label: c.label ? `${c.app_name} · ${c.label}` : c.app_name }))}
            />
          </div>
          <Button variant="secondary" icon="plus" onClick={add}>
            Add
          </Button>
        </div>
      )}
      {scopes.map((s) => (
        <ConnectionScope
          key={s.connection_id}
          scope={s}
          connection={byId.get(s.connection_id)}
          appName={byId.get(s.connection_id)?.app_name ?? names.get(s.connection_id) ?? 'Connection'}
          onChange={(tools) => set(s.connection_id, tools)}
          onRemove={() => setScopes((all) => all.filter((x) => x.connection_id !== s.connection_id))}
        />
      ))}
      <ApiErrorNotice error={scopeBot.error} />
      <div className={styles.row}>
        <Button variant="primary" loading={scopeBot.isPending} onClick={save}>
          Save tools
        </Button>
      </div>
    </div>
  );
}
