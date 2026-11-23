// A program's page, in the Bots area's centre: its head (name, what it is for, its bot, where it can run, when it
// runs; Canvas | Code; Save; Run), the canvas or the file, the right rail (the selected step, else the program's own
// settings, its schedule among them), and the run being followed underneath.
import { useMemo, useState } from 'react';
import { useBotPlaces, useBots, type Bot, type Schedule } from '@/api/bots';
import {
  live,
  refusedProblems,
  useDeleteProgram,
  useProgram,
  useProgramRun,
  useProgramRuns,
  useRunProgram,
  useUpdateProgram,
  type Program,
  type Step,
} from '@/api/programs';
import { RunsOnPills } from '@/pages/templates/BotTemplates';
import { same, scheduleOf, sentence } from '../schedule';
import { BotCat, CLOUD_NOTE, Modal, useShell } from '../shell/bits';
import { ScheduleFields } from '../shell/ScheduleFields';
import { Canvas } from './Canvas';
import { CodeView } from './CodeView';
import { sameFlow, toFlow, toNodes } from './flow';
import { RunPanel } from './RunPanel';
import { plainProblem } from './words';

/** The program's own settings, in the right rail while no step is selected: its name, its bot, where and when it runs. */
function Settings({ program, bots, onSaved, onDeleted }: { program: Program; bots: Bot[]; onSaved: (p: Program) => void; onDeleted: () => void }) {
  const shell = useShell();
  const places = useBotPlaces();
  const update = useUpdateProgram(program.slug);
  const remove = useDeleteProgram();
  const [name, setName] = useState(program.name);
  const [summary, setSummary] = useState(program.summary ?? '');
  const [bot, setBot] = useState<string | null>(program.bot);
  const [runsOn, setRunsOn] = useState<string | null>(program.runs_on);
  const [schedule, setSchedule] = useState<Schedule>(() => scheduleOf(program.schedule ?? undefined));
  const [deleting, setDeleting] = useState(false);
  const cloudOk = program.can_run_on.includes('cloud');
  const where = (places.data ?? [{ id: null, name: 'Glyphh cloud', mode: 'cloud' as const, linked: true }]).filter((p) =>
    p.id === null ? cloudOk || runsOn === null : program.can_run_on.includes('rrotor') || p.id === runsOn,
  );
  const changed =
    name.trim() !== program.name ||
    summary.trim() !== (program.summary ?? '') ||
    bot !== program.bot ||
    runsOn !== program.runs_on ||
    !same(schedule, scheduleOf(program.schedule ?? undefined));
  const save = () =>
    update.mutate(
      { name: name.trim(), summary: summary.trim(), bot, runs_on: runsOn, schedule },
      {
        onSuccess: (saved) => {
          shell.toast(`${saved.name} is saved.`);
          onSaved(saved);
        },
      },
    );
  return (
    <aside className="prail" aria-label="Program settings">
      <div className="prail-head">
        <span className="sn-mark" aria-hidden>
          ⌗
        </span>
        <div className="prail-title">
          <b>This program</b>
          <small>Pick a step on the canvas to change it.</small>
        </div>
      </div>
      <div className="prail-body form">
        <label>
          Name
          <input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          What it is for
          <textarea rows={2} value={summary} maxLength={200} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <div className="pfield">
          <span className="plabel" id="prog-bot">
            Its bot
          </span>
          <div className="pickcats" role="radiogroup" aria-labelledby="prog-bot">
            {bots.map((b) => (
              <button key={b.id} type="button" role="radio" aria-checked={bot === b.slug} className={bot === b.slug ? 'pickcat on' : 'pickcat'} onClick={() => setBot(b.slug)}>
                <span className="mini">
                  <BotCat look={b.look} mascot={b.mascot} size={30} />
                </span>
                {b.name}
              </button>
            ))}
          </div>
          <small className="dim">It does every step that names no other bot, as itself.</small>
        </div>

        <h3>Where it runs</h3>
        <label>
          <select aria-label="Where it runs" value={runsOn ?? ''} onChange={(e) => setRunsOn(e.target.value || null)}>
            {where.map((p) => (
              <option key={p.id ?? ''} value={p.id ?? ''} disabled={(!p.linked && p.id !== runsOn) || (p.id === null && !cloudOk)}>
                {p.linked ? p.name : `${p.name} (offline)`}
              </option>
            ))}
          </select>
          <small>{runsOn ? 'On that machine, through its rrotor: every kind of step, code too.' : cloudOk ? CLOUD_NOTE : 'It runs code, so it needs a rrotor.'}</small>
        </label>

        <h3>When it runs</h3>
        <ScheduleFields schedule={schedule} onChange={(c) => setSchedule((s) => ({ ...s, ...c }))} />
        <small className="dim" role="status">
          {sentence(schedule, same(schedule, scheduleOf(program.schedule ?? undefined)) && program.next_run_at ? new Date(program.next_run_at).toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit' }) : undefined)}
        </small>
        {schedule.every !== 'off' && (
          <label>
            What each run is given
            <input aria-label="What each run is given" value={schedule.input} placeholder="Nothing" onChange={(e) => setSchedule((s) => ({ ...s, input: e.target.value }))} />
          </label>
        )}

        <div className="row end">
          <button type="button" className="btn ghost danger" onClick={() => setDeleting(true)}>
            Delete program
          </button>
          <button type="button" className="btn primary" disabled={!changed || !name.trim() || update.isPending} onClick={save}>
            {update.isPending ? 'Saving…' : 'Save settings'}
          </button>
        </div>
        {update.error && <div className="err">{update.error.message}</div>}
      </div>
      {deleting && (
        <Modal title={`Delete ${program.name}?`} small front onClose={() => setDeleting(false)}>
          <p className="dim">Its runs and their trail go with it. Your bots stay. This cannot be undone.</p>
          {remove.error && <div className="err">{remove.error.message}</div>}
          <div className="row end">
            <button type="button" className="btn ghost" onClick={() => setDeleting(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="btn danger solid"
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(program.slug, {
                  onSuccess: () => {
                    shell.toast(`${program.name} is deleted.`);
                    onDeleted();
                  },
                })
              }
            >
              Delete
            </button>
          </div>
        </Modal>
      )}
    </aside>
  );
}

/** Run, with what to give it if anything: a small form under the button. */
function RunButton({ program, busy, onStarted }: { program: Program; busy: boolean; onStarted: () => void }) {
  const start = useRunProgram(program.slug);
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const go = () =>
    start.mutate(input.trim(), {
      onSuccess: () => {
        setOpen(false);
        setInput('');
        onStarted();
      },
    });
  return (
    <div className="prunbtn">
      <button type="button" className="btn primary" disabled={busy || start.isPending} title={busy ? 'It is running: one run at a time' : undefined} onClick={() => setOpen(!open)}>
        ▶ Run
      </button>
      {open && (
        <div className="menu prunmenu" role="dialog" aria-label="Run it">
          <label>
            What to give it <span className="dim">(if anything)</span>
            <textarea aria-label="What to give it" rows={3} value={input} placeholder="Nothing" onChange={(e) => setInput(e.target.value)} />
          </label>
          <div className="row end">
            <button type="button" className="btn ghost tiny" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="button" className="btn primary tiny" disabled={start.isPending} onClick={go}>
              {start.isPending ? 'Starting…' : 'Run now'}
            </button>
          </div>
          {start.error && <small className="err">{start.error.message}</small>}
        </div>
      )}
    </div>
  );
}

type View = 'canvas' | 'code';

export function ProgramPage({ slug, onOpen }: { slug: string; onOpen: (slug: string | null) => void }) {
  const shell = useShell();
  const query = useProgram(slug);
  const bots = useBots();
  const runs = useProgramRuns(slug);
  const latest = runs.data?.[0] ?? null;
  const current = useProgramRun(latest?.id ?? null);
  const run = current.data ?? latest;
  const update = useUpdateProgram(slug);
  const [view, setView] = useState<View>('canvas');
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(0);
  const [runOpen, setRunOpen] = useState(true);
  const program = query.data;
  const base = useMemo(() => (program ? toFlow(toNodes(program.flow)) : []), [program]);

  if (query.error)
    return (
      <section className="center" aria-label="Program">
        <div className="empty">
          <b>{query.error.message}</b>
          <p>Pick a program on the left.</p>
        </div>
      </section>
    );
  if (!program)
    return (
      <section className="center" aria-label="Program">
        <p className="dim pad">Reading the program…</p>
      </section>
    );

  const all = bots.data ?? [];
  const own = all.find((b) => b.slug === program.bot);
  const canvasDirty = steps !== null && !sameFlow(steps, base);
  const codeDirty = source !== null && source !== program.source;
  const dirty = view === 'canvas' ? canvasDirty : codeDirty;
  const problems = [...(update.error ? refusedProblems(update.error) : []), ...(update.error ? [] : program.problems)];
  const busy = live(run?.status);

  const save = () => {
    const change = view === 'canvas' ? { flow: steps ?? base } : { source: source ?? program.source };
    update.mutate(change, {
      onSuccess: (saved) => {
        setSteps(null);
        setSource(null);
        setLoaded((n) => n + 1);
        shell.toast(saved.problems.length ? 'Saved. It has problems to put right before it can run.' : 'Saved.');
      },
    });
  };
  const switchTo = (v: View) => {
    if (v === view) return;
    if (dirty) return shell.toast(`Save or undo your changes to the ${view === 'canvas' ? 'canvas' : 'file'} first.`);
    setView(v);
  };
  const undo = () => {
    setSteps(null);
    setSource(null);
    update.reset();
    setLoaded((n) => n + 1);
  };
  const settings = (
    <Settings
      key={`${program.slug}:${program.updated_at}`}
      program={program}
      bots={all}
      onSaved={(saved) => saved.slug !== slug && onOpen(saved.slug)}
      onDeleted={() => onOpen(null)}
    />
  );

  return (
    <section className="center program" aria-label={program.name}>
      <header className="phead">
        <div className="ptitle">
          <h1>{program.name}</h1>
          {program.summary && <small>{program.summary}</small>}
        </div>
        <div className="pfacts">
          <span className="pchip" title="Its bot">
            {own ? <BotCat look={own.look} mascot={own.mascot} size={20} /> : <i className="sn-nocat" />}
            {own?.name ?? 'No bot yet'}
          </span>
          <RunsOnPills runsOn={program.can_run_on} />
          <span className="pchip ghost" title="When it runs">
            ◷ {program.schedule_summary && program.schedule_summary !== 'Off' ? program.schedule_summary : 'When you run it'}
          </span>
        </div>
        <span className="spacer" />
        <div className="pviews" role="tablist" aria-label="View">
          <button type="button" role="tab" aria-selected={view === 'canvas'} className={view === 'canvas' ? 'on' : ''} onClick={() => switchTo('canvas')}>
            Canvas
          </button>
          <button type="button" role="tab" aria-selected={view === 'code'} className={view === 'code' ? 'on' : ''} onClick={() => switchTo('code')}>
            Code
          </button>
        </div>
        {dirty && (
          <button type="button" className="btn ghost" onClick={undo}>
            Undo changes
          </button>
        )}
        <button type="button" className="btn" disabled={!dirty || update.isPending} onClick={save}>
          {update.isPending ? 'Saving…' : dirty ? 'Save' : 'Saved'}
        </button>
        <RunButton program={program} busy={busy || program.problems.length > 0} onStarted={() => setRunOpen(true)} />
      </header>

      {problems.length > 0 && (
        <div className="problems pproblems" role="alert">
          <b>{update.error ? 'It was not saved.' : 'It cannot run yet.'}</b> Put these right on the canvas or in the file:
          <ul aria-label="Problems">
            {problems.map((p) => (
              <li key={p}>{plainProblem(p)}</li>
            ))}
          </ul>
        </div>
      )}
      {update.error && problems.length === 0 && <div className="err pad">{update.error.message}</div>}

      <div className="pbody">
        {view === 'canvas' ? (
          <Canvas key={`${program.slug}:${loaded}`} program={program} bots={all} run={run} onChange={setSteps} aside={settings} />
        ) : (
          <div className="pcanvas-row">
            <CodeView key={`${program.slug}:${loaded}`} source={source ?? program.source} onChange={setSource} />
            {settings}
          </div>
        )}
      </div>

      {run && <RunPanel program={program} run={run} bots={all} open={runOpen} onToggle={() => setRunOpen(!runOpen)} />}
    </section>
  );
}
