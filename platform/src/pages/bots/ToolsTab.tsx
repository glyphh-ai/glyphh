import { useState } from 'react';
import { Link } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import {
  connectionsOff,
  connectionToolsQuery,
  useConnections,
  useConnectionTools,
  useScopeBot,
  useSetPermissions,
  type Bot,
  type Connection,
} from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { permissionChanges } from '@/api/connections';
import { ToolPermissions } from '@/bots/tools/ToolPermissions';
import { plural } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard, Select, useToast } from '@/ui';
import { InClaude } from './ada';
import styles from './bots.module.css';
import look from './look.module.css';

type Scope = { connection_id: string; tools: string[] };

/**
 * One connection on the bot: its tools as claude.ai's tool permissions, a switch each (off: the bot never uses it) and
 * the hand for one that waits for approval, which is the connection's own setting, kept on the server for every bot.
 */
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
  const permissions = useSetPermissions(scope.connection_id);
  const chosen = new Set(scope.tools);
  const title = connection?.label ? `${appName} · ${connection.label}` : appName;
  const list = tools.data ?? [];
  const on = list.filter((t) => chosen.has(t.key) && t.permission !== 'deny');

  const put = (keys: string[], ask: boolean | 'unblock') => {
    const changed = permissionChanges(list, keys, (t) =>
      ask === 'unblock' ? (t.permission === 'deny' ? 'ask' : null) : t.permission === 'deny' ? null : ask ? 'ask' : 'allow',
    );
    if (Object.keys(changed).length > 0) permissions.mutate(changed);
  };
  const onSwitch = (keys: string[], next: boolean) => {
    if (next) {
      onChange([...new Set([...scope.tools, ...keys])]);
      put(keys, 'unblock'); // a tool blocked for every bot is let back, needing approval
    } else {
      const off = new Set(keys);
      onChange(scope.tools.filter((k) => !off.has(k)));
    }
  };

  return (
    <Card>
      <section className={styles.form} aria-label={title}>
        <div className={styles.spread}>
          <div className={styles.row}>
            {connection?.app_icon && <img src={connection.app_icon} alt="" className={styles.icon} />}
            <div className={styles.grow}>
              <h2 className={styles.name}>{title}</h2>
              <span className={styles.muted}>{tools.data ? `${on.length} of ${plural(list.length, 'tool')} on` : `${plural(scope.tools.length, 'tool')} on`}</span>
            </div>
          </div>
          <Button variant="ghost" size="sm" icon="trash" onClick={onRemove}>
            Take off
          </Button>
        </div>
        {tools.isPending && <LoadingCard />}
        <ApiErrorNotice error={tools.error ?? permissions.error} />
        {list.length > 0 && (
          <ToolPermissions
            label={`${title} tools`}
            tools={list}
            busy={permissions.isPending}
            isOn={(t) => chosen.has(t.key) && t.permission !== 'deny'}
            onSwitch={onSwitch}
            onApproval={put}
          />
        )}
        {tools.data?.length === 0 && <p className={styles.muted}>This app has no tools.</p>}
        {connection && (
          <p className={styles.muted}>
            A tool off is one the bot never uses; the hand makes it wait for you in Approvals, for every bot on {appName}.{' '}
            <Link to={`/connections/${encodeURIComponent(connection.app)}?tab=tools`}>All of {appName}’s permissions</Link>
          </p>
        )}
      </section>
    </Card>
  );
}

/**
 * The tools the bot may use, per connection: add one of the org's connections (every tool of it on), then switch off
 * the ones it should never use.
 */
export function ToolsTab({ bot }: { bot: Bot }) {
  const toast = useToast();
  const queries = useQueryClient();
  const connections = useConnections();
  const scopeBot = useScopeBot(bot.slug);
  const [scopes, setScopes] = useState<Scope[]>(() => bot.connections.map((c) => ({ connection_id: c.connection_id, tools: [...c.tools] })));
  const [adding, setAdding] = useState('');
  const [fetching, setFetching] = useState(false);
  const names = new Map(bot.connections.map((c) => [c.connection_id, c.app_name]));
  const byId = new Map((connections.data ?? []).map((c) => [c.id, c]));
  const free = (connections.data ?? []).filter((c) => !scopes.some((s) => s.connection_id === c.id));
  const pick = adding || free[0]?.id || '';

  const set = (id: string, tools: string[]) => setScopes((all) => all.map((s) => (s.connection_id === id ? { ...s, tools } : s)));
  const add = async () => {
    if (!pick) return;
    setFetching(true);
    // All its tools on, as claude.ai turns on a connector's tools; any it cannot read yet the card shows as an error.
    const tools = await queries.fetchQuery(connectionToolsQuery(pick)).catch(() => []);
    setFetching(false);
    setScopes((all) => (all.some((s) => s.connection_id === pick) ? all : [...all, { connection_id: pick, tools: tools.filter((t) => t.permission !== 'deny').map((t) => t.key) }]));
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
        <div className={styles.addRow}>
          <div className={styles.grow}>
            <Select
              label="Add a connection"
              value={pick}
              onChange={(e) => setAdding(e.target.value)}
              options={free.map((c) => ({ value: c.id, label: c.label ? `${c.app_name} · ${c.label}` : c.app_name }))}
            />
          </div>
          <Button variant="secondary" icon="plus" loading={fetching} onClick={() => void add()}>
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
