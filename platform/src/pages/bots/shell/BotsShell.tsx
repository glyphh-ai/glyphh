// The Bots area is the Glyphh Bot app's interface (glyphh-bot src/renderer/src/App.tsx): its top bar, the rail on the
// left (BOTS | CONNECTIONS), the chat in the centre, panels that open on the right from the top bar's icons, and the
// thin status bar. Its styles are that app's own stylesheet (glyphh-bot.css), scoped to this shell.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useApprovals, useBotPlaces, useBotRuns, useBots, useConnections, type Bot, type Connection } from '@/api/bots';
import { useMe } from '@/api/queries';
import { useSwarmRuns, useSwarms, type Swarm } from '@/api/swarms';
import { useShellNav } from '@/layout/AppShell/AppShell';
import { ago } from '@/lib/format';
import { ToolsPanel } from '@/pages/connections/ToolsPanel';
import { GatesTab } from '../GatesTab';
import { botPath } from '../parts';
import { ToolsTab } from '../ToolsTab';
import { BotCat, ShellContext, useEscape, type PanelId, type ShellApi } from './bits';
import { BotChat, CrewChat, MODES } from './Chat';
import { DecisionsPanel } from './Decisions';
import { BotEditor } from './Editor';
import { Icon, ICON, Reactor } from './icons';
import { ConnectorIcon, Rail, type RailTab } from './Rail';
import './glyphh-bot.css';
import './platform.css';

const PANELS: ReadonlyArray<{ id: PanelId; label: string; icon: string }> = [
  { id: 'decisions', label: 'Decisions', icon: ICON.decisions },
  { id: 'gates', label: 'Ada gates', icon: ICON.gates },
  { id: 'tools', label: 'Tools', icon: ICON.tools },
];
/** Old links to a bot's tabs still land: its gates and tools open as panels, its settings as the editor. */
const OLD_TABS: Record<string, PanelId | undefined> = { gates: 'gates', tools: 'tools' };

type Room = { kind: 'bot' | 'crew'; slug: string };

/** Recents: the room's past runs, newest first; one click shows it in the chat. New chat starts from the empty state. */
function Recents({ rows, onPick, onNew }: { rows: { id: string; title: string; who: ReactNode; sub: string }[] | undefined; onPick: (id: string) => void; onNew: () => void }) {
  const [open, setOpen] = useState(false);
  useEscape(() => setOpen(false), open);
  return (
    <div className="recents">
      <button type="button" className={`chip ${open ? 'on' : ''}`} title="Past runs" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon d={ICON.recents} size={14} /> <span className="chiptext">Recents</span> <span className="dim">▾</span>
      </button>
      {open && (
        <>
          <div className="veil clear" onMouseDown={() => setOpen(false)} />
          <div className="rpanel" role="dialog" aria-label="Recents">
            <div className="rhead">
              <b>Recents</b>
              <span className="spacer" />
              <button
                type="button"
                className="btn sm"
                onClick={() => {
                  setOpen(false);
                  onNew();
                }}
              >
                <Icon d={ICON.plus} size={12} /> New chat
              </button>
            </div>
            <div className="rlist">
              {rows === undefined ? (
                <p className="dim pad">Reading…</p>
              ) : rows.length ? (
                <div className="rsec">
                  {rows.map((r) => (
                    <div key={r.id} className="rrow">
                      <button
                        type="button"
                        className="rmain"
                        onClick={() => {
                          setOpen(false);
                          onPick(r.id);
                        }}
                      >
                        <span className="rwho">{r.who}</span>
                        <span className="rtitle">{r.title}</span>
                        <small>{r.sub}</small>
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="dim pad">No runs yet. Every task you give shows up here.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BotRecents({ bot, onPick, onNew }: { bot: Bot; onPick: (id: string) => void; onNew: () => void }) {
  const runs = useBotRuns(bot.slug);
  const rows = runs.data?.map((r) => ({
    id: r.id,
    title: r.input || 'Run',
    who: <BotCat look={bot.look} mascot={bot.mascot} size={18} />,
    sub: `${bot.name} · ${ago(r.created_at)}`,
  }));
  return <Recents rows={rows} onPick={onPick} onNew={onNew} />;
}

function CrewRecents({ swarm, onPick, onNew }: { swarm: Swarm; onPick: (id: string) => void; onNew: () => void }) {
  const runs = useSwarmRuns(swarm.slug);
  const rows = runs.data?.map((r) => ({ id: r.id, title: r.task || 'Run', who: <Icon d={ICON.chat} size={14} />, sub: `${swarm.name} · ${ago(r.created_at)}` }));
  return <Recents rows={rows} onPick={onPick} onNew={onNew} />;
}

/** A panel on the right, as the Glyphh Bot app's desk draws one: its head with a close, its body. */
function Panel({ icon, title, onClose, plain, children }: { icon: ReactNode; title: string; onClose: () => void; plain?: boolean; children: ReactNode }) {
  return (
    <section className="dslot panel" aria-label={title}>
      <div className="dhead">
        {icon}
        <span className="dtitle">{title}</span>
        <span className="spacer" />
        <button type="button" title="Close" aria-label={`Close ${title}`} onClick={onClose}>
          ×
        </button>
      </div>
      {/* The platform's own components keep their own look inside a panel (the app's styles stop at .gb-plain), in the
          dark theme whatever the person's own is: the app is always black. */}
      <div className="dbody pscroll">
        {plain ? (
          <div className="gb-plain" data-theme="dark-hc">
            {children}
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function StatusBar({ ok, connectors, bot, swarm }: { ok: boolean; connectors: number | undefined; bot: Bot | undefined; swarm: Swarm | undefined }) {
  const { data: me } = useMe();
  const places = useBotPlaces();
  const place = (id: string | null | undefined) => (id ? (places.data?.find((p) => p.id === id)?.name ?? 'your machine') : 'Glyphh cloud');
  const mode = MODES.find((m) => m.value === (bot?.permission_mode ?? 'ask'))!;
  return (
    <footer className="statusbar">
      <span className={ok ? 'stat ok' : 'stat bad'}>
        <i /> Glyphh {ok ? `connected${me ? ` · ${me.plan.name.toLowerCase()}` : ''}` : 'not reachable'}
      </span>
      <span className="stat">Connectors {connectors ?? '-'}</span>
      {bot && <span className={mode.value === 'auto' ? 'stat bad' : 'stat'}>Permissions {mode.label}</span>}
      <span className="eq" aria-hidden>
        {Array.from({ length: 24 }, (_, i) => (
          <i key={i} style={{ animationDelay: `${(i * 137) % 900}ms` }} />
        ))}
      </span>
      {(bot || swarm) && <span className="stat">Runs on {place(bot ? bot.runs_on : swarm!.runs_on)}</span>}
      {me && (
        <span className="stat">
          {me.plan.name} · {me.precedents.used.toLocaleString('en-GB')}
          {me.precedents.limit !== null ? ` of ${me.precedents.limit.toLocaleString('en-GB')}` : ''} precedents
        </span>
      )}
    </footer>
  );
}

export function BotsShell() {
  const { name } = useParams();
  const navigate = useNavigate();
  const nav = useShellNav();
  const [params, setParams] = useSearchParams();
  const bots = useBots();
  const swarms = useSwarms();
  const approvals = useApprovals();
  const connections = useConnections();
  const [toast, setToast] = useState('');
  const [fresh, setFresh] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(false);

  // The room: the bot in the address, the crew in ?crew=, else the first project's crew, else the first bot.
  const settled = !bots.isPending && !swarms.isPending;
  const crews = swarms.data ?? [];
  const asked = params.get('crew');
  const room: Room | null = name
    ? { kind: 'bot', slug: name }
    : asked
      ? { kind: 'crew', slug: asked }
      : !settled
        ? null
        : crews[0]
          ? { kind: 'crew', slug: crews[0].slug }
          : bots.data?.[0]
            ? { kind: 'bot', slug: bots.data[0].slug }
            : null;
  const bot = room?.kind === 'bot' ? bots.data?.find((b) => b.slug === room.slug) : undefined;
  const swarm = room?.kind === 'crew' ? crews.find((s) => s.slug === room.slug) : undefined;
  const roomKey = room ? `${room.kind}:${room.slug}` : '';

  const set = useCallback(
    (change: Record<string, string | null>) =>
      setParams(
        (p) => {
          const next = new URLSearchParams(p);
          next.delete('tab');
          for (const [k, v] of Object.entries(change)) v === null ? next.delete(k) : next.set(k, v);
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );

  const tab = params.get('tab') ?? '';
  const open = useMemo(() => {
    const list = (params.get('panel') ?? '').split(',').filter((p): p is PanelId => PANELS.some((x) => x.id === p));
    const old = OLD_TABS[tab];
    return old && !list.includes(old) ? [...list, old] : list;
  }, [params, tab]);
  const connId = params.get('conn');
  const connection = connections.data?.find((c) => c.id === connId);
  const railTab: RailTab = params.get('rail') === 'connections' || connId ? 'connections' : 'bots';
  const editing = params.get('new') ? 'new' : params.get('edit') || tab === 'settings' || tab === 'loop' ? 'edit' : null;
  const focus = params.get('run');

  const togglePanel = (id: PanelId) => set({ panel: (open.includes(id) ? open.filter((p) => p !== id) : [...open, id]).join(',') || null });
  const api: ShellApi = useMemo(
    () => ({
      toast: setToast,
      openPanel: (id) => set({ panel: [...new Set([...open, id])].join(',') }),
      editBot: (slug, advanced) => {
        if (slug === null) return set({ new: '1', edit: null });
        if (slug === name) return set({ edit: advanced ? 'advanced' : '1', new: null });
        navigate(`${botPath(slug)}?edit=1`);
      },
    }),
    [set, open, name, navigate],
  );

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 4000);
    return () => clearTimeout(t);
  }, [toast]);
  // A room picked in the drawer closes it (the phone's rail).
  useEffect(() => setRailOpen(false), [roomKey]);

  const waiting = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of approvals.data ?? []) if (r.kind !== 'swarm') m.set(r.bot_slug, (m.get(r.bot_slug) ?? 0) + 1);
    return m;
  }, [approvals.data]);

  const pick = (id: string) => {
    setFresh(null);
    set({ run: id });
  };
  const newChat = () => {
    setFresh(roomKey);
    set({ run: null });
  };
  const closeEditor = () => set({ edit: null, new: null });
  const shownPanels = PANELS.filter((p) => open.includes(p.id) && bot);
  const missing = room && settled && !bot && !swarm;
  const repo = swarm?.repo_url.replace(/^https?:\/\/(www\.)?github\.com\//, '').replace(/\.git$/, '');

  return (
    <ShellContext.Provider value={api}>
      <div className="gb">
        <div className="app">
          <header className="top">
            <button type="button" className="icon onphone" aria-label="Menu" onClick={nav.toggleSidebar}>
              <Icon d={ICON.menu} size={16} />
            </button>
            <button type="button" className={`icon onphone ${railOpen ? 'on' : ''}`} aria-label="Bots and connections" aria-expanded={railOpen} onClick={() => setRailOpen(!railOpen)}>
              <Icon d={ICON.bots} size={16} />
            </button>
            <div className="brand">
              {/* The logo is the file, never typed. */}
              <img src="/glyphh-logo-text-white.png" alt="Glyphh" />
              <span>Bot</span>
            </div>
            {swarm && repo && (
              <a className="chip" href={swarm.repo_url} target="_blank" rel="noreferrer" title="The project’s repo">
                <Icon d={ICON.folder} size={14} /> <span className="chiptext">{repo.split('/').pop()}</span>
                <span className="branch">{swarm.base_branch}</span>
              </a>
            )}
            {bot && <BotRecents bot={bot} onPick={pick} onNew={newChat} />}
            {swarm && <CrewRecents swarm={swarm} onPick={pick} onNew={newChat} />}
            <div className="spacer" />
            {bot && (
              <>
                <button type="button" className="icon" title={`Edit ${bot.name}`} aria-label={`Edit ${bot.name}`} onClick={() => api.editBot(bot.slug)}>
                  <Icon d={ICON.edit} size={16} />
                </button>
                <div className="pbtns" role="toolbar" aria-label="Panels">
                  {PANELS.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={`icon ${open.includes(p.id) ? 'on' : ''}`}
                      title={`${p.label}${open.includes(p.id) ? ' (open: click to close)' : ''}`}
                      aria-label={p.label}
                      aria-pressed={open.includes(p.id)}
                      onClick={() => togglePanel(p.id)}
                    >
                      <Icon d={p.icon} size={16} />
                    </button>
                  ))}
                </div>
              </>
            )}
            {swarm && (
              <Link className="icon" to={`/swarms/${encodeURIComponent(swarm.slug)}`} title={`Edit ${swarm.name}`} aria-label={`Edit ${swarm.name}`}>
                <Icon d={ICON.edit} size={16} />
              </Link>
            )}
          </header>

          <main className="grid">
            <Rail
              open={railOpen}
              tab={railTab}
              onTab={(t) => set({ rail: t === 'connections' ? 'connections' : null, conn: null })}
              bots={bots.data}
              swarms={crews}
              room={room}
              waiting={waiting}
              connection={connId}
              onConnection={(c: Connection) => set({ conn: connId === c.id ? null : c.id })}
            />
            {railOpen && <button type="button" className="railscrim" aria-label="Close" onClick={() => setRailOpen(false)} />}
            <section className="desk">
              <div className="deskrow">
                {bot ? (
                  <BotChat key={bot.slug} bot={bot} focus={focus} fresh={fresh === roomKey} onSent={() => setFresh(null)} />
                ) : swarm ? (
                  <CrewChat key={swarm.slug} swarm={swarm} bots={bots.data ?? []} focus={focus} fresh={fresh === roomKey} onSent={() => setFresh(null)} />
                ) : (
                  <section className="center" aria-label="Bots">
                    {bots.error ? (
                      <div className="empty">
                        <b>Your bots could not be read</b>
                        <p>{bots.error.message}</p>
                      </div>
                    ) : missing ? (
                      <div className="empty">
                        <b>{room.kind === 'bot' ? 'There is no such bot' : 'There is no such project'}</b>
                        <p>
                          Nothing here is called {room.slug}. Pick one on the left, or <Link to="/bots">go back to your bots</Link>.
                        </p>
                      </div>
                    ) : settled ? (
                      <div className="hero-wrap">
                        <Reactor size={600} className="backdrop" />
                        <div className="hero-crew solo-hero">
                          <span>
                            <BotCat look={{ extra: 'antenna' }} size={140} mode="full" />
                          </span>
                        </div>
                        <div className="floor" />
                        <h1 className="headline">Make your first bot</h1>
                        <p className="sub">A bot decides with gates in Ada that learn from your answers, and does the rest with Claude and the tools you allow.</p>
                        <div className="ideas">
                          <button type="button" onClick={() => api.editBot(null)}>
                            + New bot
                          </button>
                          <Link to="/marketplace/bots">Add a ready-made one</Link>
                        </div>
                      </div>
                    ) : null}
                  </section>
                )}
                {(shownPanels.length > 0 || connection) && (
                  <div className="panels">
                    {bot &&
                      shownPanels.map((p) => (
                        <Panel key={p.id} icon={<Icon d={p.icon} size={13} />} title={p.label} onClose={() => togglePanel(p.id)} plain={p.id !== 'decisions'}>
                          {p.id === 'decisions' && <DecisionsPanel bot={bot} />}
                          {p.id === 'gates' && <GatesTab bot={bot} />}
                          {p.id === 'tools' && <ToolsTab key={bot.updated_at} bot={bot} />}
                        </Panel>
                      ))}
                    {connection && (
                      <Panel
                        icon={<ConnectorIcon name={connection.app_name} icon={connection.app_icon} size={16} />}
                        title={`${connection.app_name} · tools`}
                        onClose={() => set({ conn: null })}
                        plain
                      >
                        <ToolsPanel connection={connection} />
                      </Panel>
                    )}
                  </div>
                )}
              </div>
            </section>
          </main>

          <StatusBar ok={!bots.error} connectors={connections.data?.length} bot={bot} swarm={swarm} />

          {editing === 'new' && <BotEditor key="new" bot={null} onClose={closeEditor} />}
          {editing === 'edit' && bot && <BotEditor key={bot.id} bot={bot} advanced={tab === 'loop' || params.get('edit') === 'advanced'} onClose={closeEditor} />}
          {toast && (
            <div className="toast" role="status" onClick={() => setToast('')}>
              {toast}
            </div>
          )}
        </div>
      </div>
    </ShellContext.Provider>
  );
}
