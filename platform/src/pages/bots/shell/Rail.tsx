// The left rail, as the Glyphh Bot app's (glyphh-bot src/renderer/src/Left.tsx): BOTS | CONNECTIONS on top; under
// Bots each project as a crew card with its cats stacked, then the bots (a round cat, the name with a small tag, a
// line that says what it is for or what it is doing) and New bot; under Connections the org's connections; the
// account at the foot.
import { useRef, useState } from 'react';
import { Link } from 'react-router';
import { connectionsOff, useBotKey, useConnections, useSyncConnections, working, type Bot, type Connection } from '@/api/bots';
import { useMe } from '@/api/queries';
import type { Swarm } from '@/api/swarms';
import { botPath } from '../parts';
import { botTag, BotCat, useEscape, useShell } from './bits';
import { Icon, ICON } from './icons';

export type RailTab = 'bots' | 'connections';
export const crewPath = (slug: string) => `/bots?crew=${encodeURIComponent(slug)}`;

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

type BotsProps = { bots: Bot[] | undefined; swarms: Swarm[]; room: { kind: 'bot' | 'crew'; slug: string } | null; waiting: Map<string, number> };

function Bots({ bots, swarms, room, waiting }: BotsProps) {
  const shell = useShell();
  return (
    <div className="rail-scroll">
      {swarms.map((s) => (
        <Link key={s.id} to={crewPath(s.slug)} className={room?.kind === 'crew' && room.slug === s.slug ? 'bot crew on' : 'bot crew'} aria-current={room?.kind === 'crew' && room.slug === s.slug ? 'page' : undefined}>
          <div className="stack">
            {s.members.slice(0, 4).map((m) => {
              const b = bots?.find((x) => x.slug === m.slug);
              return (
                <span key={m.id} className="mini">
                  <BotCat look={b?.look} mascot={b?.mascot} size={26} />
                </span>
              );
            })}
          </div>
          <div className="meta">
            <b>{s.name}</b>
            <small>{s.members.length ? `${s.members.length} bots, taking turns` : 'nobody in yet'}</small>
          </div>
        </Link>
      ))}

      <div className="rail-label">Bots</div>
      {bots === undefined && <p className="dim pad">Reading your bots…</p>}
      {bots?.length === 0 && <p className="dim pad">No bots yet.</p>}
      <nav aria-label="Your bots">
        {bots?.map((b) => {
          const asks = waiting.get(b.slug) ?? 0;
          const status = asks > 0 || b.last_run?.status === 'needs_input' ? 'speaking' : working(b.last_run?.status) ? 'thinking' : '';
          const on = room?.kind === 'bot' && room.slug === b.slug;
          return (
            <div key={b.id} className={`bot ${on ? 'on' : ''} ${status}`}>
              <Link to={botPath(b.slug)} className="botlink" aria-current={on ? 'page' : undefined}>
                <span className="ava">
                  <BotCat look={b.look} mascot={b.mascot} size={44} busy={status === 'thinking'} />
                </span>
                <div className="meta">
                  <b>
                    {b.name} <i>{botTag(b)}</i>
                  </b>
                  <small>{status === 'speaking' ? 'Needs you' : status === 'thinking' ? 'working' : (b.summary ?? '')}</small>
                </div>
              </Link>
              <div className="bot-actions">
                <button type="button" className="pill" title={`Edit ${b.name}`} aria-label={`Edit ${b.name}`} onClick={() => shell.editBot(b.slug)}>
                  edit
                </button>
              </div>
            </div>
          );
        })}
      </nav>
      <button type="button" className="newbot" onClick={() => shell.editBot(null)}>
        <span>+</span> New bot
      </button>
    </div>
  );
}

function Connections({ onOpen, open }: { onOpen: (c: Connection) => void; open: string | null }) {
  const connections = useConnections();
  const sync = useSyncConnections();
  const key = useBotKey();
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
      {connections.data?.map((c) => (
        <button key={c.id} type="button" className={`conn ${open === c.id ? 'on' : ''}`} title={`${c.app_name}${c.label ? ` · ${c.label}` : ''}: its tools and permissions`} onClick={() => onOpen(c)}>
          <ConnectorIcon name={c.app_name} icon={c.app_icon} />
          <b>{c.app_name}</b>
          <span className="dot ok" />
          <small>on</small>
        </button>
      ))}
      <Link className="btn wide" to="/connections">
        + Add connectors
      </Link>

      <div className="rail-label">Claude</div>
      <div className="conn">
        <span className={`dot ${key.data ? 'ok' : 'bad'}`} />
        <b>Claude key</b>
        <small>{key.data?.set ? 'your key' : 'Glyphh’s key'}</small>
      </div>
      <Link className="btn wide" to="/settings/claude-key">
        Claude key settings
      </Link>
    </div>
  );
}

/** The account button at the foot of the rail: its menu opens upward with the account, Settings and Log out. */
function Account() {
  const { data: me } = useMe();
  const [open, setOpen] = useState(false);
  const logOut = useRef<HTMLFormElement>(null);
  useEscape(() => setOpen(false), open);
  const name = me?.email ?? '';
  const initial = (me?.name ?? me?.email ?? '?').charAt(0).toUpperCase();
  return (
    <div className="account">
      {open && <div className="acc-veil" onMouseDown={() => setOpen(false)} />}
      {open && (
        <div className="acc-menu" role="menu" aria-label="Account">
          <div className="acc-who">
            <span className="acc-ava big">{initial}</span>
            <div>
              <b>{me?.name ?? name}</b>
              <small>
                {me ? `${me.plan.name} plan · ${me.org.name}` : ''}
              </small>
            </div>
          </div>
          <hr />
          <Link role="menuitem" to="/settings/general">
            <Icon d={ICON.settings} size={15} /> Settings
          </Link>
          <button type="button" role="menuitem" className="danger" onClick={() => logOut.current?.submit()}>
            <Icon d={ICON.logOut} size={15} /> Log out
          </button>
        </div>
      )}
      <button type="button" className={`acc-btn ${open ? 'on' : ''}`} title={name} aria-haspopup="menu" aria-expanded={open} aria-label="Your account" onClick={() => setOpen(!open)}>
        <span className="acc-ava">{initial}</span>
        <span className="acc-name">{name}</span>
        {me && <span className="plan">{me.plan.name}</span>}
        <span className="acc-caret dim">▴</span>
      </button>
      <form ref={logOut} method="post" action="/auth/logout" hidden />
    </div>
  );
}

type Props = BotsProps & { tab: RailTab; onTab: (t: RailTab) => void; onConnection: (c: Connection) => void; connection: string | null; open: boolean };

export function Rail({ tab, onTab, onConnection, connection, open, ...bots }: Props) {
  return (
    <aside className={`rail left ${open ? 'open' : ''}`} aria-label="Bots and connections">
      <div className="tabs" role="tablist" aria-label="Rail">
        <button type="button" role="tab" aria-selected={tab === 'bots'} className={tab === 'bots' ? 'on' : ''} onClick={() => onTab('bots')}>
          Bots
        </button>
        <button type="button" role="tab" aria-selected={tab === 'connections'} className={tab === 'connections' ? 'on' : ''} onClick={() => onTab('connections')}>
          Connections
        </button>
      </div>
      {tab === 'bots' ? <Bots {...bots} /> : <Connections onOpen={onConnection} open={connection} />}
      <Account />
    </aside>
  );
}
