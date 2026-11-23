// The left rail, as the Glyphh Bot app's (glyphh-bot src/renderer/src/Left.tsx): BOTS | PROGRAMS | CONNECTIONS on top
// (Programs: the org's programs, ../programs/Programs.tsx); under
// Bots the crew card (tick the cats that are in it; a small edit opens Crew settings), then the bots (a round cat, the
// name, a line that says what it is for or what it is doing) and New bot; under Connections the org's connections; the
// account at the foot.
import { useRef, useState } from 'react';
import { Link } from 'react-router';
import { isOrchestrator, working, type Bot } from '@/api/bots';
import { useMe } from '@/api/queries';
import { botPath, BotCat, CREW_PATH, useEscape, useShell } from './bits';
import { ProgramsRail } from '../programs/Programs';
import { Connections } from './Connections';
import { CREW_MAX, type Crew } from './crew';
import { Icon, ICON } from './icons';

export type RailTab = 'bots' | 'programs' | 'connections';

type BotsProps = {
  bots: Bot[] | undefined;
  crew: Crew;
  /** The bot whose chat is open; none while the crew is. */
  bot: string | null;
  crewOn: boolean;
  /** The bots a run of which waits on the person. */
  waiting: Set<string>;
  onCrewSettings: () => void;
};

function Bots({ bots, crew, bot, crewOn, waiting, onCrewSettings }: BotsProps) {
  const shell = useShell();
  const count = crew.members.length;
  // The orchestrator is pinned first; then a bot that needs the person floats up; the rest keep their order.
  const sorted = [...(bots ?? [])].sort((a, b) => Number(isOrchestrator(b)) - Number(isOrchestrator(a)) || Number(waiting.has(b.slug)) - Number(waiting.has(a.slug)));
  return (
    <div className="rail-scroll">
      <div className={crewOn ? 'bot crew on' : 'bot crew'}>
        <div className="crewtop">
          <Link to={CREW_PATH} className="meta" aria-current={crewOn ? 'page' : undefined}>
            <b>The Crew</b>
            <small>{count === 0 ? 'nobody in yet' : `${count} ${count === 1 ? 'bot' : 'bots'}, ${crew.settings.turn_mode === 'wait' ? 'taking turns' : 'led by the orchestrator'}`}</small>
          </Link>
          <button type="button" className="pill" title="Crew settings" aria-label="Crew settings" onClick={onCrewSettings}>
            edit
          </button>
        </div>
        {bots && bots.length > 0 && (
          <div className="crewcats" role="group" aria-label="In the crew">
            {bots.map((b) => {
              const on = crew.members.includes(b.id);
              const full = !on && count >= CREW_MAX;
              return (
                <button
                  key={b.id}
                  type="button"
                  className={on ? 'mini tick on' : 'mini tick'}
                  aria-pressed={on}
                  aria-label={b.name}
                  title={on ? `${b.name} is in the crew: click to take it out` : full ? `The crew is full at ${CREW_MAX}` : `${b.name} is out: click to put it in the crew`}
                  disabled={crew.pending || full || (on && count === 1)}
                  onClick={() => crew.toggle(b.id)}
                >
                  <BotCat look={b.look} mascot={b.mascot} size={26} />
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="rail-label">Bots</div>
      {bots === undefined && <p className="dim pad">Reading your bots…</p>}
      {bots?.length === 0 && <p className="dim pad">No bots yet.</p>}
      <nav aria-label="Your bots">
        {sorted.map((b) => {
          const asks = waiting.has(b.slug);
          const busy = !asks && working(b.last_run?.status);
          const on = bot === b.slug;
          return (
            <div key={b.id} className={`bot ${on ? 'on' : ''} ${asks ? 'speaking' : busy ? 'thinking' : ''}`}>
              <Link to={botPath(b.slug)} className="botlink" aria-current={on ? 'page' : undefined}>
                <span className="ava">
                  <BotCat look={b.look} mascot={b.mascot} size={44} busy={busy} />
                </span>
                <div className="meta">
                  <b>
                    {b.name} {isOrchestrator(b) && <i className="role">Orchestrator</i>}
                    {isOrchestrator(b) && asks && ' '}
                    {asks && <i className="needs">Needs you</i>}
                  </b>
                  <small>{busy ? 'working' : (b.summary ?? '')}</small>
                </div>
              </Link>
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
              <small>{me ? `${me.plan.name} plan · ${me.org.name}` : ''}</small>
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

type Props = BotsProps & {
  tab: RailTab;
  onTab: (t: RailTab) => void;
  onConnection: (id: string | null) => void;
  onCatalog: (open: boolean) => void;
  open: boolean;
  /** The program whose page is open, and opening one or making one. */
  program: string | null;
  onProgram: (slug: string) => void;
  onNewProgram: () => void;
};

const TABS: ReadonlyArray<{ tab: RailTab; label: string }> = [
  { tab: 'bots', label: 'Bots' },
  { tab: 'programs', label: 'Programs' },
  { tab: 'connections', label: 'Connections' },
];

export function Rail({ tab, onTab, onConnection, onCatalog, open, program, onProgram, onNewProgram, ...bots }: Props) {
  return (
    <aside className={`rail left ${open ? 'open' : ''}`} aria-label="Bots and connections">
      <div className="tabs" role="tablist" aria-label="Rail">
        {TABS.map((t) => (
          <button key={t.tab} type="button" role="tab" aria-selected={tab === t.tab} className={tab === t.tab ? 'on' : ''} onClick={() => onTab(t.tab)}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'bots' ? (
        <Bots {...bots} />
      ) : tab === 'programs' ? (
        <ProgramsRail current={program} onOpen={onProgram} onNew={onNewProgram} />
      ) : (
        <Connections onOpen={onConnection} onCatalog={onCatalog} />
      )}
      <Account />
    </aside>
  );
}
