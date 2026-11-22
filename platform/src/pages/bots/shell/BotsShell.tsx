// The Bots area is the Glyphh Bot app's interface (glyphh-bot src/renderer/src/App.tsx): its top bar (the workspace,
// Recents, and on the right edit and Decisions), the rail on the left (BOTS | CONNECTIONS), the chat in the centre,
// and the thin status bar. One place per thing: connections are the rail's tab, decisions the Decisions panel, a bot's
// settings its editor, the crew's its one modal. Its styles are that app's own stylesheet (glyphh-bot.css), scoped to
// this shell.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useBots } from '@/api/bots';
import { useMe } from '@/api/queries';
import { useWaiting, type Recent } from '@/api/recents';
import { DecisionsPanel } from '@/bots/decisions/DecisionsPanel';
import { useShellNav } from '@/layout/AppShell/AppShell';
import { botPath, BotCat, ShellContext, type ShellApi } from './bits';
import { BotChat, CrewChat } from './Chat';
import { ConnectionModals } from './Connections';
import { useCrew } from './crew';
import { CrewSettings } from './CrewSettings';
import { BotEditor } from './Editor';
import { Icon, ICON, Reactor } from './icons';
import { Rail, type RailTab } from './Rail';
import { Recents } from './Recents';
import { WorkPanelHost, WorkPanelIcons, WorkProvider } from './work';
import { WorkspacePill } from './Workspace';
import './glyphh-bot.css';
import './platform.css';

/** A panel on the right, as the Glyphh Bot app's desk draws one: its head with a close, its body. */
function Panel({ icon, title, onClose, head, children }: { icon: ReactNode; title: string; onClose: () => void; head?: ReactNode; children: ReactNode }) {
  return (
    <section className="dslot panel" aria-label={title}>
      <div className="dhead">
        {icon}
        <span className="dtitle">{title}</span>
        {head}
        <span className="spacer" />
        <button type="button" title="Close" aria-label={`Close ${title}`} onClick={onClose}>
          ×
        </button>
      </div>
      {/* The platform's own components keep their own look inside a panel (the app's styles stop at .gb-plain), in the
          dark theme whatever the person's own is: the app is always black. */}
      <div className="dbody pscroll">
        <div className="gb-plain" data-theme="dark-hc">
          {children}
        </div>
      </div>
    </section>
  );
}

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return <span className="clock">{now.toLocaleTimeString('en-GB')}</span>;
}

/** The thin strip along the bottom: that Glyphh answers, and the time. Settings are not repeated here. */
function StatusBar({ ok }: { ok: boolean }) {
  const { data: me } = useMe();
  return (
    <footer className="statusbar">
      <span className={ok ? 'stat ok' : 'stat bad'}>
        <i /> Glyphh {ok ? `connected${me ? ` · ${me.plan.name.toLowerCase()}` : ''}` : 'not reachable'}
      </span>
      <span className="eq" aria-hidden>
        {Array.from({ length: 24 }, (_, i) => (
          <i key={i} style={{ animationDelay: `${(i * 137) % 900}ms` }} />
        ))}
      </span>
      <Clock />
    </footer>
  );
}

export function BotsShell() {
  const { name } = useParams();
  const navigate = useNavigate();
  const nav = useShellNav();
  const [params, setParams] = useSearchParams();
  const bots = useBots();
  const crew = useCrew(bots.data);
  const waits = useWaiting();
  const [toast, setToast] = useState('');
  const [fresh, setFresh] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const [crewSettings, setCrewSettings] = useState(false);
  // Whose decisions the panel shows while the crew is the room: one of its bots.
  const [crewBot, setCrewBot] = useState<string | null>(null);

  // The room: the bot in the address, else the crew.
  const all = bots.data ?? [];
  const bot = name ? all.find((b) => b.slug === name) : undefined;
  const crewOn = !name;
  const roomKey = name ? `bot:${name}` : 'crew';
  const members = all.filter((b) => crew.members.includes(b.id));

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

  // Old links still land: a bot's old tabs open Decisions or its settings; an old link to a crew opens its workspace.
  const tab = params.get('tab') ?? '';
  const old = params.get('crew');
  useEffect(() => {
    if (!old) return;
    crew.open(old);
    set({ crew: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [old]);

  const decisions = (params.get('panel') ?? '').split(',').some((p) => p === 'decisions' || p === 'gates') || tab === 'gates' || tab === 'decisions';
  const connId = params.get('conn');
  const catalog = params.get('add') === '1';
  const railTab: RailTab = params.get('rail') === 'connections' || connId || catalog ? 'connections' : 'bots';
  const editing = params.get('new') ? 'new' : params.get('edit') || tab === 'settings' || tab === 'loop' ? 'edit' : null;
  const focus = params.get('run');

  const api: ShellApi = useMemo(
    () => ({
      toast: setToast,
      // From the editor's "Decides: …" line: the editor closes and the panel opens, in one step.
      openDecisions: () => set({ panel: 'decisions', edit: null, new: null }),
      editBot: (slug) => {
        if (slug === null) return set({ new: '1', edit: null });
        if (slug === name) return set({ edit: '1', new: null });
        navigate(`${botPath(slug)}?edit=1`);
      },
      openConnections: (add) => set({ rail: 'connections', add: add ? '1' : null }),
    }),
    [set, name, navigate],
  );

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 4000);
    return () => clearTimeout(t);
  }, [toast]);
  // A room picked in the drawer closes it (the phone's rail).
  useEffect(() => setRailOpen(false), [roomKey]);

  const waiting = useMemo(() => new Set((waits.data?.recents ?? []).flatMap((r) => (r.kind === 'bot' && r.bot_slug ? [r.bot_slug] : []))), [waits.data]);

  const pick = (r: Recent) => {
    setFresh(null);
    if (r.kind === 'bot' && r.bot_slug) return navigate(`${botPath(r.bot_slug)}?run=${encodeURIComponent(r.id)}`);
    if (r.project_slug) crew.open(r.project_slug);
    navigate(`/bots?run=${encodeURIComponent(r.id)}`);
  };
  const newChat = () => {
    setFresh(roomKey);
    set({ run: null });
  };
  const closeEditor = () => set({ edit: null, new: null });
  const settled = !bots.isPending;
  const missing = Boolean(name) && settled && !bot;
  // Whose decisions: the bot's own, or in the crew's room one of its bots.
  const decided = bot ?? (crewOn ? (members.find((b) => b.slug === crewBot) ?? members[0]) : undefined);
  // The work panels (files, terminal, editor…) are a rrotor's: only when what is selected runs on one.
  const runsOn = bot ? (bot.runs_on ?? null) : crewOn ? crew.settings.runs_on : null;

  return (
    <ShellContext.Provider value={api}>
      <div className="gb">
        <div className="app">
          {/* The work panels' state, around the top bar and the body (its children keep their indent: a mount, not a rewrite). */}
          <WorkProvider runsOn={runsOn} runId={focus}>
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
            <WorkspacePill crew={crew} />
            <Recents bots={all} needsYou={waits.data?.needs_you ?? 0} focus={focus} onPick={pick} onNew={newChat} />
            <div className="spacer" />
            {bot && (
              <button type="button" className="icon" title={`Edit ${bot.name}`} aria-label={`Edit ${bot.name}`} onClick={() => api.editBot(bot.slug)}>
                <Icon d={ICON.edit} size={16} />
              </button>
            )}
            {crewOn && all.length > 0 && (
              <button type="button" className="icon" title="Crew settings" aria-label="Edit the crew" onClick={() => setCrewSettings(true)}>
                <Icon d={ICON.edit} size={16} />
              </button>
            )}
            {decided && (
              <button
                type="button"
                className={`icon ${decisions ? 'on' : ''}`}
                title={`Decisions${decisions ? ' (open: click to close)' : ''}`}
                aria-label="Decisions"
                aria-pressed={decisions}
                onClick={() => set({ panel: decisions ? null : 'decisions' })}
              >
                <Icon d={ICON.decisions} size={16} />
              </button>
            )}
            {/* The work panels' icons (Files, Preview, Terminal, Editor, Diff and the layout manager) mount here, only on a rrotor. */}
            {runsOn && <WorkPanelIcons />}
          </header>

          <main className="grid">
            <Rail
              open={railOpen}
              tab={railTab}
              onTab={(t) => set({ rail: t === 'connections' ? 'connections' : null, conn: null, add: null })}
              bots={bots.data}
              crew={crew}
              bot={name ?? null}
              crewOn={crewOn}
              waiting={waiting}
              onCrewSettings={() => setCrewSettings(true)}
              onConnection={(id) => set({ conn: id })}
              onCatalog={(open) => set({ add: open ? '1' : null })}
            />
            {railOpen && <button type="button" className="railscrim" aria-label="Close" onClick={() => setRailOpen(false)} />}
            <section className="desk">
              <div className="deskrow">
                {bot ? (
                  <BotChat key={bot.slug} bot={bot} focus={focus} fresh={fresh === roomKey} onSent={() => setFresh(null)} />
                ) : crewOn && all.length > 0 ? (
                  <CrewChat key={crew.project?.slug ?? 'none'} crew={crew} bots={all} focus={focus} fresh={fresh === roomKey} onSent={() => setFresh(null)} />
                ) : (
                  <section className="center" aria-label="Bots">
                    {bots.error ? (
                      <div className="empty">
                        <b>Your bots could not be read</b>
                        <p>{bots.error.message}</p>
                      </div>
                    ) : missing ? (
                      <div className="empty">
                        <b>There is no such bot</b>
                        <p>
                          Nothing here is called {name}. Pick one on the left, or <Link to="/bots">go back to your bots</Link>.
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
                        <p className="sub">Tell a bot its job in plain words. It does the work with the apps you allow, asks you when it is not sure, and learns from your answers.</p>
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
                {(decisions && decided) || runsOn ? (
                  <div className={decisions && decided ? 'panels' : 'panels bare'}>
                    {decisions && decided && (
                      <Panel
                        icon={<Icon d={ICON.decisions} size={13} />}
                        title="Decisions"
                        onClose={() => set({ panel: null })}
                        head={
                          crewOn && members.length > 1 ? (
                            <select className="dwho" aria-label="Whose decisions" value={decided.slug} onChange={(e) => setCrewBot(e.target.value)}>
                              {members.map((b) => (
                                <option key={b.id} value={b.slug}>
                                  {b.name}
                                </option>
                              ))}
                            </select>
                          ) : undefined
                        }
                      >
                        <DecisionsPanel key={decided.slug} slug={decided.slug} />
                      </Panel>
                    )}
                    {/* The rrotor's work panels (Files, Preview, Terminal, Editor, Diff) mount here. */}
                    {runsOn && <WorkPanelHost />}
                  </div>
                ) : null}
              </div>
            </section>
          </main>

          <StatusBar ok={!bots.error} />

          {editing === 'new' && <BotEditor key="new" bot={null} onClose={closeEditor} />}
          {editing === 'edit' && bot && <BotEditor key={bot.id} bot={bot} onClose={closeEditor} />}
          {crewSettings && <CrewSettings crew={crew} bots={all} onClose={() => setCrewSettings(false)} />}
          <ConnectionModals open={connId} catalog={catalog} onOpen={(id) => set({ conn: id })} onCatalog={(open) => set({ add: open ? '1' : null })} />
          {toast && (
            <div className="toast" role="status" onClick={() => setToast('')}>
              {toast}
            </div>
          )}
          </WorkProvider>
        </div>
      </div>
    </ShellContext.Provider>
  );
}
