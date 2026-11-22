// CONNECTIONS in the rail (glyphh-bot Left.tsx, docs/6-connections.png): the one place the org's connections are. A
// row is the app's own icon, its name and its state; a click opens the one modal there is for a connection (its
// account, which of its tools the bots may use and which wait for a yes, Disconnect). "+ Add connectors" opens the
// catalog, each app a card with a "+".
import { useEffect, useRef, useState } from 'react';
import {
  connectionsOff,
  useConnections,
  useLinkConnection,
  useRemoveConnection,
  useSetPermissions,
  useSyncConnections,
  type Connection,
  type ConnectionTool,
  type ConnectorApp,
  type Permission,
} from '@/api/bots';
import { permissionChanges, useAppCatalog, useAppTools } from '@/api/connections';
import { ToolPermissions } from '@/bots/tools/ToolPermissions';
import { date } from '@/lib/format';
import { Modal, useShell } from './bits';

/** A connection's app icon, or a letter tile when it has none. */
export function ConnectorIcon({ name, icon, size = 20 }: { name: string; icon: string | null; size?: number }) {
  return icon ? (
    <img className="cicon" src={icon} width={size} height={size} alt="" />
  ) : (
    <span className="cicon blank" style={{ width: size, height: size }} aria-hidden>
      {name.replace(/[^a-z0-9]/gi, '').charAt(0).toUpperCase() || '?'}
    </span>
  );
}

/**
 * How a connection stands, as its row says it: ON, SIGN IN or FAILED, and only when the server says so. Until it
 * sends a status the row claims nothing: a connection that is listed is not known to work.
 */
function stateOf(c: Connection): { words: string; dot: string } | null {
  if (c.status === 'ok') return { words: 'On', dot: 'ok' };
  if (c.status === 'sign_in') return { words: 'Sign in', dot: 'warn' };
  if (c.status === 'failed') return { words: 'Failed', dot: 'bad' };
  return null;
}

/** The one modal for a connection: its account, its tools' permissions, Disconnect. */
function ConnectionModal({ connection, onClose }: { connection: Connection; onClose: () => void }) {
  const shell = useShell();
  const tools = useAppTools(connection.id);
  const save = useSetPermissions(connection.id);
  const remove = useRemoveConnection();
  const [sure, setSure] = useState(false);
  const put = (keys: string[], to: (t: ConnectionTool) => Permission | null) => {
    const changed = permissionChanges(tools.data ?? [], keys, to);
    if (Object.keys(changed).length > 0) save.mutate(changed);
  };
  const failed = tools.error ?? save.error ?? remove.error;
  return (
    <Modal title={connection.app_name} icon={<ConnectorIcon name={connection.app_name} icon={connection.app_icon} size={24} />} onClose={onClose}>
      <dl className="connfacts">
        <div>
          <dt>Account</dt>
          <dd>{connection.label ?? 'Signed in'}</dd>
        </div>
        <div>
          <dt>Connected</dt>
          <dd>{date(connection.created_at)}</dd>
        </div>
      </dl>
      <p className="dim toolnote">
        What your bots may do with {connection.app_name}. A tool that is off is never used; the hand makes a bot wait for your yes first, the tick lets it go ahead.
      </p>
      {failed && <div className="err">{failed.message}</div>}
      {tools.isPending ? (
        <p className="dim">Reading its tools…</p>
      ) : tools.data?.length === 0 ? (
        <p className="dim">{connection.app_name} has no tools yet.</p>
      ) : (
        <div className="gb-plain" data-theme="dark-hc">
          <ToolPermissions
            label={`${connection.app_name} tools`}
            tools={tools.data ?? []}
            busy={save.isPending}
            isOn={(t) => t.permission !== 'deny'}
            onSwitch={(keys, on) => put(keys, (t) => (on ? (t.permission === 'deny' ? 'ask' : null) : 'deny'))}
            onApproval={(keys, ask) => put(keys, (t) => (t.permission === 'deny' ? null : ask ? 'ask' : 'allow'))}
          />
        </div>
      )}
      <div className="row end connfoot">
        {sure ? (
          <>
            <span className="dim">Your bots lose {connection.app_name}.</span>
            <button type="button" className="btn ghost" onClick={() => setSure(false)}>
              Keep it
            </button>
            <button
              type="button"
              className="btn danger solid"
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(connection.id, {
                  onSuccess: () => {
                    shell.toast(`${connection.app_name} is disconnected.`);
                    onClose();
                  },
                })
              }
            >
              Disconnect {connection.app_name}
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn ghost danger" onClick={() => setSure(true)}>
              Disconnect
            </button>
            <button type="button" className="btn primary" onClick={onClose}>
              Done
            </button>
          </>
        )}
      </div>
    </Modal>
  );
}

const EVERY_MS = 2000;
type Waiting = { app: ConnectorApp; url: string; blocked: boolean; before: number; gaveUp: boolean };

/**
 * The catalog: every app there is to connect, searched by name, each a card with a "+". The "+" opens the app's own
 * sign-in in a small window; while the person signs in the server is asked what is connected, and once the app shows
 * its modal opens on its tools.
 */
function Catalog({ onClose, onConnected }: { onClose: () => void; onConnected: (c: Connection) => void }) {
  const shell = useShell();
  const connections = useConnections();
  const link = useLinkConnection();
  const sync = useSyncConnections();
  const [words, setWords] = useState('');
  const [q, setQ] = useState('');
  const [waiting, setWaiting] = useState<Waiting | null>(null);
  const popup = useRef<Window | null>(null);
  const closedAt = useRef(0);
  useEffect(() => {
    const t = setTimeout(() => setQ(words.trim()), 250);
    return () => clearTimeout(t);
  }, [words]);
  const catalog = useAppCatalog(q);
  const apps = (catalog.data?.pages ?? []).flatMap((p) => p.apps);
  const have = new Set((connections.data ?? []).map((c) => c.app));
  const of = (app: string, list = connections.data) => (list ?? []).filter((c) => c.app === app);

  useEffect(() => {
    if (!waiting || waiting.gaveUp) return;
    const check = () => {
      if (sync.isPending) return;
      sync.mutate(undefined, {
        onSuccess: ({ connections: now }) => {
          const mine = of(waiting.app.slug, now);
          if (mine.length > waiting.before) {
            setWaiting(null);
            shell.toast(`${waiting.app.name} is connected.`);
            onConnected(mine.at(-1)!);
          } else if (closedAt.current && Date.now() - closedAt.current >= EVERY_MS) {
            setWaiting((w) => w && { ...w, gaveUp: true });
          }
        },
      });
    };
    const watch = setInterval(() => {
      if (popup.current?.closed && !closedAt.current) closedAt.current = Date.now();
      check();
    }, EVERY_MS);
    window.addEventListener('focus', check);
    return () => {
      clearInterval(watch);
      window.removeEventListener('focus', check);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting, sync.isPending]);

  const connect = (app: ConnectorApp) =>
    link.mutate(app.slug, {
      onSuccess: ({ url }) => {
        closedAt.current = 0;
        popup.current = window.open(url, 'glyphh-connect', 'popup,width=560,height=720');
        setWaiting({ app, url, blocked: !popup.current, before: of(app.slug).length, gaveUp: false });
      },
    });
  const stop = () => {
    popup.current?.close();
    popup.current = null;
    setWaiting(null);
    sync.reset();
  };
  const failed = catalog.error ?? link.error ?? sync.error;

  return (
    <Modal
      title="Add connectors"
      onClose={() => {
        stop();
        onClose();
      }}
    >
      {waiting ? (
        <div className="connecting" role="status" aria-live="polite">
          {waiting.gaveUp ? (
            <p>{waiting.app.name} was not connected. Its sign-in window closed before it finished.</p>
          ) : (
            <>
              <p>
                <b>Connecting {waiting.app.name}…</b>
              </p>
              {waiting.blocked ? (
                <p className="dim">
                  Your browser stopped the sign-in window.{' '}
                  <a href={waiting.url} target="_blank" rel="noreferrer">
                    Open {waiting.app.name}’s sign-in
                  </a>
                  , then come back here.
                </p>
              ) : (
                <p className="dim">Finish signing in to {waiting.app.name} in the window that opened. This closes by itself once it is connected.</p>
              )}
            </>
          )}
          <div className="row end">
            <button type="button" className="btn ghost" onClick={stop}>
              Cancel
            </button>
            {waiting.gaveUp && (
              <button type="button" className="btn primary" disabled={link.isPending} onClick={() => connect(waiting.app)}>
                Try again
              </button>
            )}
          </div>
        </div>
      ) : (
        <>
          <input type="search" className="catsearch" aria-label="Search apps" placeholder="Search apps: Gmail, Slack, HubSpot…" value={words} autoFocus onChange={(e) => setWords(e.target.value)} />
          <ul className="catalog" aria-label="Apps" aria-busy={catalog.isFetching || undefined}>
            {apps.map((a) => (
              <li key={a.slug}>
                <ConnectorIcon name={a.name} icon={a.icon} size={28} />
                <span className="appname">
                  <b>{a.name}</b>
                  <small>{have.has(a.slug) ? 'Connected' : a.description || 'Connector'}</small>
                </span>
                <button
                  type="button"
                  className="btn tiny plus"
                  aria-label={have.has(a.slug) ? `Add another ${a.name} account` : `Connect ${a.name}`}
                  title={have.has(a.slug) ? 'Add another account' : 'Connect'}
                  disabled={link.isPending}
                  onClick={() => connect(a)}
                >
                  +
                </button>
              </li>
            ))}
            {catalog.isPending && <li className="dim">Reading the apps…</li>}
            {!catalog.isPending && apps.length === 0 && !catalog.error && <li className="dim">{q ? `No app matches “${q}”.` : 'No apps here.'}</li>}
          </ul>
          {catalog.hasNextPage && (
            <button type="button" className="btn wide" disabled={catalog.isFetchingNextPage} onClick={() => void catalog.fetchNextPage()}>
              Show more
            </button>
          )}
        </>
      )}
      {failed && <div className="err">{failed.message}</div>}
    </Modal>
  );
}

type Props = {
  /** The connection whose modal is open (its id), and whether the catalog is. */
  open: string | null;
  catalog: boolean;
  onOpen: (id: string | null) => void;
  onCatalog: (open: boolean) => void;
};

/** The connection's modal and the catalog, mounted over the whole shell (not inside the rail, which a phone slides). */
export function ConnectionModals({ open, catalog, onOpen, onCatalog }: Props) {
  const connections = useConnections();
  const shown = connections.data?.find((c) => c.id === open);
  return (
    <>
      {shown && <ConnectionModal key={shown.id} connection={shown} onClose={() => onOpen(null)} />}
      {catalog && (
        <Catalog
          onClose={() => onCatalog(false)}
          onConnected={(c) => {
            onCatalog(false);
            onOpen(c.id);
          }}
        />
      )}
    </>
  );
}

export function Connections({ onOpen, onCatalog }: Pick<Props, 'onOpen' | 'onCatalog'>) {
  const connections = useConnections();
  const sync = useSyncConnections();
  const off = connectionsOff(connections.error);
  return (
    <div className="rail-scroll">
      <div className="rail-label">
        Connectors
        <button type="button" className="link" disabled={sync.isPending || off} onClick={() => sync.mutate()}>
          {sync.isPending ? 'checking…' : 'refresh'}
        </button>
      </div>
      {connections.isPending && <p className="dim pad">Reading what is connected…</p>}
      {off && <p className="dim pad">Connections are not set up on this server yet.</p>}
      {connections.error && !off && <p className="err pad">{connections.error.message}</p>}
      {connections.data?.length === 0 && <p className="dim pad">No connectors yet.</p>}
      {connections.data?.map((c) => {
        const state = stateOf(c);
        return (
          <button key={c.id} type="button" className="conn" title={`${c.app_name}${c.label ? ` · ${c.label}` : ''}`} onClick={() => onOpen(c.id)}>
            <ConnectorIcon name={c.app_name} icon={c.app_icon} />
            <b>{c.app_name}</b>
            {state && <span className={`dot ${state.dot}`} />}
            {state && <small>{state.words}</small>}
          </button>
        );
      })}
      <button type="button" className="btn wide" disabled={off} onClick={() => onCatalog(true)}>
        + Add connectors
      </button>
    </div>
  );
}
