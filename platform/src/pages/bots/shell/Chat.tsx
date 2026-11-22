// The chat, the centre of the Bots area, as the Glyphh Bot app's (glyphh-bot src/renderer/src/Chat.tsx): one bot's
// chat, or a project's crew. A run is a conversation: what the person asked on the right, the bot's turn on the left
// with its cat, a line that folds its steps, what Ada decided as rows to keep or correct, its words as markdown, and
// what it asks, answered in place. Past runs are the chat's history. With nothing said yet: the cat or cats over the
// rings, the headline, ideas and the composer.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import {
  useAnswerRun,
  useBotModels,
  useBotPlaces,
  useBotRun,
  useBotRuns,
  useCancelRun,
  useRunBot,
  useUpdateBot,
  working,
  type Answer,
  type Bot,
  type BotRun,
  type Every,
  type PermissionMode,
} from '@/api/bots';
import {
  swarmGoing,
  useAnswerSwarmRun,
  useCancelSwarmRun,
  useRunSwarm,
  useSwarmRun,
  useSwarmRuns,
  useUpdateSwarm,
  type Review,
  type Swarm,
  type SwarmRun,
  type SwarmTurn,
} from '@/api/swarms';
import { ago, dollars, plural, stamp } from '@/lib/format';
import { EVERY, scheduleOf } from '../schedule';
import { botTag, BotCat, RUN_WORDS, runSummary, shortModel, useShell } from './bits';
import { Composer, SelectChip } from './Composer';
import { RunDecisions } from './Decisions';
import { Icon, ICON, Reactor } from './icons';
import { Markdown } from './Markdown';

/** Which tool steps wait for the person, as the pill says it. */
export const MODES: ReadonlyArray<{ value: PermissionMode; label: string; hint: string }> = [
  { value: 'ask', label: 'Ask first', hint: 'Every tool step waits for your yes, unless its connection allows that tool.' },
  { value: 'connection', label: 'Follow connections', hint: 'Only the tools a connection says to ask about wait for you.' },
  { value: 'auto', label: 'Run on its own', hint: 'Allowed tools run without asking. Blocked tools still never run.' },
];

const REVIEWS: ReadonlyArray<{ value: Review; label: string }> = [
  { value: 'each_turn', label: 'Ask me each turn' },
  { value: 'auto', label: 'Merge on its own' },
];

/** The chat scrolls to the newest as it grows, unless the person scrolled up to read; `focus` is a message to show. */
function useFollow(dep: unknown, focus: string | null) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [dep]);
  useEffect(() => {
    if (!focus) return;
    stick.current = false;
    document.getElementById(`msg-${focus}`)?.scrollIntoView?.({ block: 'start' });
  }, [focus, dep === undefined]); // eslint-disable-line react-hooks/exhaustive-deps
  const onScroll = () => {
    const el = scroller.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };
  return { scroller, onScroll };
}

/** The line that folds a turn's steps away: "Ran 4 steps, asked Ada 3 times". */
function Steps({ summary, lines, live }: { summary: string; lines: string[]; live?: boolean }) {
  const [open, setOpen] = useState(false);
  if (lines.length === 0) return null;
  return (
    <div className={`tgroup ${open ? 'open' : ''}`}>
      <button type="button" className="tsum" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon d={open ? ICON.collapse : ICON.expand} size={12} />
        {live ? <span className="trun">{lines.at(-1)}</span> : <span>{summary}</span>}
      </button>
      {open && (
        <div className="tools" aria-label="Steps">
          {lines.map((line, i) => (
            <div key={i} className={`tool ${live && i === lines.length - 1 ? 'run' : 'ok'}`} title={line}>
              <span className="ti">•</span>
              <span className="td">{line}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** What a run asks, as the bot asking: one option a button, or for many items each item's own; answered here. */
function Ask({ run, bot }: { run: BotRun; bot: Bot }) {
  const answer = useAnswerRun();
  const cancel = useCancelRun();
  const [picked, setPicked] = useState<Record<string, string>>({});
  const q = run.question;
  if (!q) return null;
  const batch = q.batch ?? [];
  const busy = answer.isPending || cancel.isPending;
  const send = (a: Answer) => answer.mutate({ id: run.id, answer: a });
  const ready = batch.length > 0 && batch.every((item) => picked[String(item.n)]);
  return (
    <section className="ask open" aria-label="Question">
      <div className="ask-head">{bot.name} asks</div>
      <p className="ask-q">{q.question}</p>
      {batch.length === 0 ? (
        <div className="row wrap">
          {q.options.map((option, i) => (
            <button key={option} type="button" className={i === 0 ? 'btn primary' : 'btn'} disabled={busy} onClick={() => send(option)}>
              {option}
            </button>
          ))}
          <button type="button" className="btn danger" disabled={busy} onClick={() => cancel.mutate(run.id)}>
            Cancel run
          </button>
        </div>
      ) : (
        <>
          <ol className="ask-items" aria-label="Items">
            {batch.map((item) => {
              const key = String(item.n);
              return (
                <li key={key}>
                  <span className="dlabel">
                    <i>{item.n}</i>
                    {item.label}
                  </span>
                  <span className="row" role="radiogroup" aria-label={item.label}>
                    {q.options.map((option) => (
                      <button
                        key={option}
                        type="button"
                        role="radio"
                        aria-checked={picked[key] === option}
                        className={picked[key] === option ? 'pill on' : 'pill'}
                        disabled={busy}
                        onClick={() => setPicked((p) => ({ ...p, [key]: option }))}
                      >
                        {option}
                      </button>
                    ))}
                  </span>
                </li>
              );
            })}
          </ol>
          <div className="row wrap">
            <button type="button" className="btn primary" disabled={!ready || busy} onClick={() => send(picked)}>
              Send answers
            </button>
            {q.options.map((option) => (
              <button key={option} type="button" className="btn" disabled={busy} onClick={() => setPicked(Object.fromEntries(batch.map((item) => [String(item.n), option])))}>
                All {option}
              </button>
            ))}
            <button type="button" className="btn danger" disabled={busy} onClick={() => cancel.mutate(run.id)}>
              Cancel run
            </button>
          </div>
        </>
      )}
      {(answer.error ?? cancel.error) && <div className="err">{(answer.error ?? cancel.error)!.message}</div>}
    </section>
  );
}

/** One run as a conversation: the person's message, then the bot's turn. */
function BotTurn({ run: listed, bot, place }: { run: BotRun; bot: Bot; place: (id: string | null | undefined) => string | null }) {
  // The list says a run is going; the run itself is read again until it stops or asks.
  const live = useBotRun(working(listed.status) ? listed.id : null);
  const run = live.data?.id === listed.id ? live.data : listed;
  const going = working(run.status);
  const where = place(run.runs_on);
  return (
    <div id={`msg-${run.id}`} className="turnpair">
      {run.input && (
        <div className="msg me">
          <div className="bubble">{run.input}</div>
        </div>
      )}
      <div className={`msg bot-msg ${going ? 'live' : ''}`} role="article" aria-label={`${bot.name}: ${RUN_WORDS[run.status]}`}>
        <div className="face">
          <BotCat look={bot.look} mascot={bot.mascot} size={42} busy={going} />
        </div>
        <div className="body">
          <div className="who">
            {bot.name}
            <span className={`turn ${run.status === 'needs_input' ? 'hot' : ''}`}>{RUN_WORDS[run.status]}</span>
            {going && (
              <span className="typing" aria-hidden>
                <i />
                <i />
                <i />
              </span>
            )}
          </div>
          <Steps summary={runSummary(run, bot.spec)} lines={run.log} live={going} />
          <RunDecisions run={run} bot={bot} />
          {run.output && <Markdown text={run.output} />}
          {run.status === 'needs_input' && <Ask run={run} bot={bot} />}
          {run.error && <div className="err">{run.error}</div>}
          {!going && (
            <small className="rmeta" title={stamp(run.created_at)}>
              {ago(run.created_at)} · {dollars(run.cost_micros)}
              {where && ` · on ${where}`}
            </small>
          )}
        </div>
      </div>
    </div>
  );
}

function Hero({ cats, headline, sub, ideas, onIdea, children }: { cats: ReactNode; headline: string; sub: ReactNode; ideas: string[]; onIdea: (t: string) => void; children: ReactNode }) {
  return (
    <div className="hero-wrap">
      <Reactor size={600} className="backdrop" />
      {cats}
      <div className="floor" />
      <h1 className="headline">{headline}</h1>
      <p className="sub">{sub}</p>
      {ideas.length > 0 && (
        <div className="ideas">
          {ideas.map((t) => (
            <button key={t} type="button" onClick={() => onIdea(t)}>
              {t}
            </button>
          ))}
        </div>
      )}
      {children}
    </div>
  );
}

const usePlaceName = () => {
  const places = useBotPlaces();
  return (id: string | null | undefined) => (id ? (places.data?.find((p) => p.id === id)?.name ?? 'your machine') : null);
};

/** One bot's chat: its runs as the conversation, the composer, and its pills (Ada, runs on, model, permission, schedule). */
export function BotChat({ bot, focus, fresh, onSent }: { bot: Bot; focus: string | null; fresh: boolean; onSent: () => void }) {
  const shell = useShell();
  const runs = useBotRuns(bot.slug);
  const start = useRunBot(bot.slug);
  const update = useUpdateBot(bot.slug);
  const cancel = useCancelRun();
  const places = useBotPlaces();
  const models = useBotModels();
  const place = usePlaceName();
  const thread = [...(runs.data ?? [])].slice(0, 40).reverse();
  const hero = fresh || (runs.data !== undefined && thread.length === 0);
  const active = thread.findLast((r) => working(r.status));
  const { scroller, onScroll } = useFollow(runs.data, focus);
  const home = bot.runs_on ? places.data?.find((p) => p.id === bot.runs_on) : undefined;
  const mode = bot.permission_mode ?? 'ask';
  const schedule = scheduleOf(bot.schedule);

  const send = (text: string) => start.mutate(text, { onSuccess: onSent });
  const ideas = [...new Set([bot.schedule?.input, 'Do today’s run', 'Run on what is new', 'Show what you would do, and change nothing'].filter((t): t is string => Boolean(t)))].slice(0, 3);

  const composer = (
    <Composer
      hero={hero}
      focusKey={bot.slug}
      placeholder={`Give ${bot.name} a task…`}
      busy={Boolean(active)}
      sending={start.isPending}
      onSend={send}
      onStop={active ? () => cancel.mutate(active.id) : undefined}
      note={
        start.error ? (
          <span className="err">{start.error.message}</span>
        ) : home && !home.linked ? (
          `${home.name} is offline: start it, or pick Glyphh cloud, to run ${bot.name}.`
        ) : update.error ? (
          <span className="err">{update.error.message}</span>
        ) : null
      }
    >
      <button
        type="button"
        className={bot.gate_models.length ? 'ctl on hot' : 'ctl'}
        title="What its gates learned in Ada"
        onClick={() => shell.openPanel('gates')}
      >
        <i className="led" /> Ada · {bot.gate_models.length ? plural(bot.gate_models.length, 'gate') : 'no gates'}
      </button>
      <SelectChip
        title="Runs on"
        busy={update.isPending}
        value={bot.runs_on ?? ''}
        options={(places.data ?? [{ id: null, name: 'Glyphh cloud', mode: 'cloud' as const, linked: true }]).map((p) => ({
          value: p.id ?? '',
          label: p.linked ? p.name : `${p.name} (offline)`,
          disabled: !p.linked && p.id !== (bot.runs_on ?? null),
        }))}
        onPick={(id) => update.mutate({ runs_on: id || null })}
      />
      <SelectChip
        title="Model"
        busy={update.isPending}
        value={bot.model}
        options={models.data?.models.length ? models.data.models.map((m) => ({ value: m.id, label: shortModel(m.name) })) : [{ value: bot.model, label: shortModel(bot.model) || 'Model' }]}
        onPick={(model) => update.mutate({ model })}
      />
      <SelectChip
        title="Permission mode"
        busy={update.isPending}
        warn={mode === 'auto'}
        value={mode}
        options={MODES}
        onPick={(permission_mode) => update.mutate({ permission_mode })}
      />
      <SelectChip
        title="Schedule"
        busy={update.isPending}
        value={schedule.every}
        options={EVERY.map((e) => ({ value: e.value, label: e.value === 'off' ? 'No schedule' : e.label }))}
        onPick={(every: Every) => update.mutate({ schedule: { ...schedule, every } })}
      />
    </Composer>
  );

  return (
    <section className="center" aria-label={`${bot.name}’s chat`}>
      <div className="room-head">
        <div className="solo">
          <b>{bot.name}</b>
          <span>{botTag(bot)}</span>
          <small>{bot.summary}</small>
        </div>
      </div>
      {runs.error && <div className="err pad">{runs.error.message}</div>}
      {hero ? (
        <Hero
          cats={
            <div className="hero-crew solo-hero">
              <span>
                <BotCat look={bot.look} mascot={bot.mascot} size={140} mode="full" />
              </span>
            </div>
          }
          headline={`What should ${bot.name} do?`}
          sub={bot.summary || 'Say it or type it. It decides with its gates in Ada, and asks you when it is not sure.'}
          ideas={ideas}
          onIdea={send}
        >
          {composer}
        </Hero>
      ) : (
        <>
          <div className="chat" ref={scroller} onScroll={onScroll}>
            {thread.map((r) => (
              <BotTurn key={r.id} run={r} bot={bot} place={place} />
            ))}
          </div>
          {composer}
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ a crew

const TURN_WORDS: Record<SwarmTurn['status'], string> = {
  running: 'working',
  open: 'open',
  unchanged: 'no changes',
  merging: 'merging',
  merged: 'merged',
  conflict: 'conflict',
  rejecting: 'rejecting',
  rejected: 'rejected',
  failed: 'failed',
  cancelled: 'cancelled',
};

/** A turn's pull request: its number, title and files; merged or rejected here while it waits. */
function PrCard({ turn, run }: { turn: SwarmTurn; run: SwarmRun }) {
  const [open, setOpen] = useState(false);
  const answer = useAnswerSwarmRun();
  const added = turn.files.reduce((n, f) => n + (f.added ?? 0), 0);
  const removed = turn.files.reduce((n, f) => n + (f.removed ?? 0), 0);
  const waits = turn.status === 'open' && run.status === 'needs_input';
  return (
    <div className={`prcard ${turn.status} ${open ? 'open' : ''}`}>
      <div className="prrow" onClick={() => setOpen(!open)} title={open ? 'Fold' : 'Show the files'}>
        <Icon d={open ? ICON.collapse : ICON.expand} size={12} />
        <span className="prnum">PR #{turn.number}</span>
        <span className="prtitle">{turn.title}</span>
        <span className="prstat">
          {plural(turn.files.length, 'file')}
          <i className="add">+{added}</i>
          <i className="del">−{removed}</i>
        </span>
        {waits ? (
          <span className="row" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="btn primary sm" disabled={answer.isPending} onClick={() => answer.mutate({ id: run.id, answer: 'merge' })}>
              Merge
            </button>
            <button type="button" className="btn danger sm" disabled={answer.isPending} onClick={() => answer.mutate({ id: run.id, answer: 'reject' })}>
              Reject
            </button>
          </span>
        ) : (
          <span className={`badge ${turn.status}`}>{TURN_WORDS[turn.status]}</span>
        )}
      </div>
      {open && (
        <div className="prbody">
          <small className="dim">{turn.branch}</small>
          <div className="pr-files">
            {turn.files.map((f) => (
              <span key={f.path}>
                {f.path}
                <i className="add">+{f.added ?? 0}</i>
                <i className="del">−{f.removed ?? 0}</i>
              </span>
            ))}
          </div>
          {turn.pr_url && (
            <a className="link" href={turn.pr_url} target="_blank" rel="noreferrer">
              {turn.pr_url}
            </a>
          )}
        </div>
      )}
      {answer.error && <div className="err pad">{answer.error.message}</div>}
    </div>
  );
}

function CrewRun({ run: listed, bots }: { run: SwarmRun; bots: Bot[] }) {
  const live = useSwarmRun(swarmGoing(listed.status) ? listed.id : null);
  const run = live.data?.id === listed.id ? live.data : listed;
  return (
    <div id={`msg-${run.id}`} className="turnpair">
      <div className="msg me">
        <div className="bubble">{run.task}</div>
      </div>
      {run.turns.map((t) => {
        const bot = bots.find((b) => b.slug === t.bot_slug);
        const going = t.status === 'running';
        return (
          <div key={t.n} id={`msg-${run.id}-${t.n}`} className={`msg bot-msg ${going ? 'live' : ''}`} role="article" aria-label={`${t.bot_name}: turn ${t.n}`}>
            <div className="face">
              <BotCat look={bot?.look} mascot={bot?.mascot} size={42} busy={going} />
            </div>
            <div className="body">
              <div className="who">
                {t.bot_name}
                <span className="turn">turn {t.n}</span>
                {going && (
                  <span className="typing" aria-hidden>
                    <i />
                    <i />
                    <i />
                  </span>
                )}
              </div>
              {t.said && <Markdown text={t.said} />}
              {t.number !== null && <PrCard turn={t} run={run} />}
              {t.error && <div className="err">{t.error}</div>}
            </div>
          </div>
        );
      })}
      {run.error && <div className="err">{run.error}</div>}
    </div>
  );
}

/** Who is in the crew, who is up, and how each turn's pull request went (the strip at the top). */
function Stage({ swarm, bots, run }: { swarm: Swarm; bots: Bot[]; run: SwarmRun | undefined }) {
  const up = run?.turns.find((t) => t.status === 'running')?.bot_slug;
  return (
    <div className="stage">
      <div className="queue" aria-label="The crew">
        {swarm.members.map((m) => {
          const bot = bots.find((b) => b.slug === m.slug);
          return (
            <div key={m.id} className={`seat ${up === m.slug ? 'up thinking' : ''}`}>
              <BotCat look={bot?.look} mascot={bot?.mascot} size={26} busy={up === m.slug} />
              <span>{m.name}</span>
            </div>
          );
        })}
        {run && swarmGoing(run.status) && <span className="stage-info">Turn {run.turns.length}</span>}
      </div>
      {run && run.turns.length > 0 && (
        <div className="turnstrip" aria-label="Turns">
          {run.turns.map((t) => (
            <button
              key={t.n}
              type="button"
              className={`tchip ${TURN_WORDS[t.status].replace(' ', '-')}`}
              title={t.title || undefined}
              onClick={() => document.getElementById(`msg-${run.id}-${t.n}`)?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })}
            >
              <b>{t.n}</b> {t.bot_name} <small>{t.number !== null ? `#${t.number} ${TURN_WORDS[t.status]}` : TURN_WORDS[t.status]}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const CREW_IDEAS = ['Build a one-page site for a product launch', 'Make a tiny browser game with a high score', 'Plan and write a study guide for my next test'];

/** A project's chat: its crew taking turns on one repo, each turn a pull request. */
export function CrewChat({ swarm, bots, focus, fresh, onSent }: { swarm: Swarm; bots: Bot[]; focus: string | null; fresh: boolean; onSent: () => void }) {
  const runs = useSwarmRuns(swarm.slug);
  const start = useRunSwarm(swarm.slug);
  const update = useUpdateSwarm(swarm.slug);
  const cancel = useCancelSwarmRun();
  const places = useBotPlaces();
  const thread = [...(runs.data ?? [])].slice(0, 20).reverse();
  const hero = fresh || (runs.data !== undefined && thread.length === 0);
  const listed = thread.at(-1);
  // The strip on top follows the run as its turn does: the run itself, read again while a turn is out.
  const live = useSwarmRun(listed && swarmGoing(listed.status) ? listed.id : null);
  const latest = live.data && live.data.id === listed?.id ? live.data : listed;
  const active = thread.findLast((r) => swarmGoing(r.status));
  const { scroller, onScroll } = useFollow(runs.data, focus);
  const members = swarm.members.map((m) => ({ m, bot: bots.find((b) => b.slug === m.slug) }));
  const machines = (places.data ?? []).filter((p) => p.id !== null);

  const send = (text: string) => start.mutate(text, { onSuccess: onSent });

  const composer = (
    <Composer
      hero={hero}
      focusKey={swarm.slug}
      placeholder="Give the crew a task…"
      busy={Boolean(active)}
      sending={start.isPending}
      onSend={send}
      onStop={active ? () => cancel.mutate(active.id) : undefined}
      note={(start.error ?? update.error) ? <span className="err">{(start.error ?? update.error)!.message}</span> : null}
    >
      <span className="ctl on hot">
        <i className="led" /> Project
      </span>
      <SelectChip
        title="Runs on"
        busy={update.isPending}
        value={swarm.runs_on}
        options={machines.length ? machines.map((p) => ({ value: p.id!, label: p.linked ? p.name : `${p.name} (offline)`, disabled: !p.linked && p.id !== swarm.runs_on })) : [{ value: swarm.runs_on, label: 'Your machine' }]}
        onPick={(runs_on) => update.mutate({ runs_on })}
      />
      <SelectChip title="Pull requests" busy={update.isPending} value={swarm.review} options={REVIEWS} onPick={(review) => update.mutate({ review })} />
    </Composer>
  );

  return (
    <section className="center" aria-label={`${swarm.name}’s chat`}>
      <div className="room-head">
        <Stage swarm={swarm} bots={bots} run={hero ? undefined : latest} />
      </div>
      {runs.error && <div className="err pad">{runs.error.message}</div>}
      {hero ? (
        <Hero
          cats={
            <div className="hero-crew">
              {members.map(({ m, bot }) => (
                <span key={m.id}>
                  <BotCat look={bot?.look} mascot={bot?.mascot} size={104} mode="full" />
                </span>
              ))}
            </div>
          }
          headline="What are we making?"
          sub="Say it or type it. The crew takes turns, each turn a pull request."
          ideas={CREW_IDEAS}
          onIdea={send}
        >
          {composer}
        </Hero>
      ) : (
        <>
          <div className="chat" ref={scroller} onScroll={onScroll}>
            {thread.map((r) => (
              <CrewRun key={r.id} run={r} bots={bots} />
            ))}
          </div>
          {composer}
        </>
      )}
    </section>
  );
}
