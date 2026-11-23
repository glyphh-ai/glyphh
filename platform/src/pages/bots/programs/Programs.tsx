// The rail's PROGRAMS tab, the one list of the org's programs: each with what it is for, its bot, where it can run (the
// same Cloud / rrotor pills the bot templates wear), when it runs and how its last run went; then New program. With no
// program picked, the centre says what a program is and offers to make one.
import { useState } from 'react';
import { useBots, type Bot } from '@/api/bots';
import { live, useCreateProgram, usePrograms, type Program } from '@/api/programs';
import { ago } from '@/lib/format';
import { RunsOnPills } from '@/pages/templates/BotTemplates';
import { BotCat, Modal, useShell } from '../shell/bits';
import { Reactor } from '../shell/icons';
import { runWords } from './words';

function Card({ program, bot, on, onOpen }: { program: Program; bot: Bot | undefined; on: boolean; onOpen: () => void }) {
  const last = program.last_run;
  const asks = last?.status === 'needs_input';
  const busy = live(last?.status) && !asks;
  return (
    <button type="button" className={`bot pcard${on ? ' on' : ''}${asks ? ' speaking' : busy ? ' thinking' : ''}`} aria-current={on ? 'page' : undefined} onClick={onOpen}>
      <span className="pcard-top">
        <b>{program.name}</b>
        {asks && <i className="needs">Needs you</i>}
      </span>
      {program.summary && <small className="pcard-sum">{program.summary}</small>}
      <span className="pcard-row">
        <span className="pcard-bot">
          {bot ? <BotCat look={bot.look} mascot={bot.mascot} size={16} /> : <i className="sn-nocat" />}
          {bot?.name ?? 'No bot'}
        </span>
        <RunsOnPills runsOn={program.can_run_on} />
      </span>
      <span className="pcard-row dim">
        <span>◷ {program.schedule_summary && program.schedule_summary !== 'Off' ? program.schedule_summary : 'When you run it'}</span>
        <span>{last ? `${runWords(last.status)} · ${ago(last.created_at)}` : 'Never run'}</span>
      </span>
    </button>
  );
}

export function ProgramsRail({ current, onOpen, onNew }: { current: string | null; onOpen: (slug: string) => void; onNew: () => void }) {
  const [q, setQ] = useState('');
  const programs = usePrograms(q.trim());
  const bots = useBots();
  return (
    <div className="rail-scroll">
      <div className="rsearch">
        <input aria-label="Find a program" placeholder="Find a program" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="rail-label">Programs</div>
      {programs.isPending && <p className="dim pad">Reading your programs…</p>}
      {programs.error && <p className="err pad">{programs.error.message}</p>}
      {programs.data?.length === 0 && <p className="dim pad">{q.trim() ? 'None found.' : 'No programs yet.'}</p>}
      <nav aria-label="Your programs">
        {(programs.data ?? []).map((p) => (
          <Card key={p.slug} program={p} bot={bots.data?.find((b) => b.slug === p.bot)} on={current === p.slug} onOpen={() => onOpen(p.slug)} />
        ))}
      </nav>
      <button type="button" className="newbot" onClick={onNew}>
        <span>+</span> New program
      </button>
    </div>
  );
}

/** The centre with no program picked. */
export function ProgramsHome({ onNew }: { onNew: () => void }) {
  return (
    <section className="center" aria-label="Programs">
      <div className="hero-wrap">
        <Reactor size={600} className="backdrop" />
        <div className="pflowart" aria-hidden>
          <i />
          <span />
          <i />
          <span />
          <i className="q" />
        </div>
        <div className="floor" />
        <h1 className="headline">Programs</h1>
        <p className="sub">Steps your bots follow the same way every time: use an app, ask a bot, ask you, choose the way. Run them by hand or on a schedule.</p>
        <div className="ideas">
          <button type="button" onClick={onNew}>
            + New program
          </button>
        </div>
      </div>
    </section>
  );
}

/** Make a program: its name, what it is for and its bot. Its steps are drawn on its canvas next. */
export function NewProgram({ onClose, onMade }: { onClose: () => void; onMade: (slug: string) => void }) {
  const shell = useShell();
  const bots = useBots();
  const create = useCreateProgram();
  const [name, setName] = useState('');
  const [summary, setSummary] = useState('');
  const [bot, setBot] = useState<string | null>(null);
  const chosen = bot ?? bots.data?.[0]?.slug ?? null;
  const make = () => {
    if (!name.trim() || create.isPending) return;
    create.mutate(
      { name: name.trim(), summary: summary.trim() || undefined, bot: chosen, flow: [] },
      {
        onSuccess: (made) => {
          shell.toast(`${made.name} is made. Add its steps on the canvas.`);
          onMade(made.slug);
        },
      },
    );
  };
  return (
    <Modal title="New program" onClose={onClose}>
      <div className="form">
        <label>
          Name
          <input value={name} maxLength={80} placeholder="PR review digest" onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && make()} />
        </label>
        <label>
          What it is for
          <input value={summary} maxLength={200} placeholder="The pull requests waiting on my review, posted to Slack" onChange={(e) => setSummary(e.target.value)} />
        </label>
        <span className="plabel" id="new-prog-bot">
          Its bot
        </span>
        <div className="pickcats" role="radiogroup" aria-labelledby="new-prog-bot">
          {bots.data?.length === 0 && <small className="dim">Make a bot first: a program is done by your bots.</small>}
          {(bots.data ?? []).map((b) => (
            <button key={b.id} type="button" role="radio" aria-checked={chosen === b.slug} className={chosen === b.slug ? 'pickcat on' : 'pickcat'} onClick={() => setBot(b.slug)}>
              <span className="mini">
                <BotCat look={b.look} mascot={b.mascot} size={30} />
              </span>
              {b.name}
            </button>
          ))}
        </div>
        {create.error && <div className="err">{create.error.message}</div>}
        <div className="row end">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn primary" disabled={!name.trim() || create.isPending} onClick={make}>
            {create.isPending ? 'Making…' : 'Make program'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
