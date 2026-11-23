// The chat, the centre of the Bots area, as the Glyphh Bot app's (glyphh-bot src/renderer/src/Chat.tsx): one bot's
// chat, or the crew's. A run is a conversation: what the person asked on the right, the bot's turn on the left
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
  type PermissionMode,
} from '@/api/bots';
import { installUrl } from '@/api/github';
import {
  runGoing,
  useAnswerProjectRun,
  useCancelProjectRun,
  useProjectRun,
  useProjectRuns,
  useRunProject,
  type Effort,
  type ProjectRun,
  type Review,
  type Turn,
} from '@/api/projects';
import { ago, dollars, plural, stamp } from '@/lib/format';
import { BotCat, effortOptions, EFFORTS, RUN_WORDS, shortModel } from './bits';
import { Composer, SelectChip } from './Composer';
import type { Crew } from './crew';
import { Icon, ICON, Reactor } from './icons';
import { useNarration } from './narration';
import { Rich, TurnBody } from './turn';

/** When a bot must ask before it acts, as the pill and its settings say it. */
export const MODES: ReadonlyArray<{ value: PermissionMode; label: string; hint: string }> = [
  { value: 'ask', label: 'Ask me first', hint: 'It waits for your yes before every action.' },
  { value: 'connection', label: 'Follow each app’s settings', hint: 'It asks only where an app is set to ask.' },
  { value: 'auto', label: 'Act on its own', hint: 'It does not ask. What you blocked still never happens.' },
];

/** The crew's permission mode: when its pull requests wait for the person. */
const CREW_MODES: ReadonlyArray<{ value: Review; label: string }> = [
  { value: 'each_turn', label: 'Ask me at each pull request' },
  { value: 'end', label: 'One review at the end' },
];

/** Why a run ended, in words; nothing while it has not. */
const endedWords = (run: Pick<ProjectRun, 'ended' | 'max_turns'>) =>
  ({
    '': '',
    done: "The crew said it's done",
    orchestrator: "The orchestrator said it's done",
    max_turns: `Stopped at the safety cap of ${run.max_turns} turns`,
    max_spend: 'Stopped at the spend cap',
  })[run.ended];

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
      {/* An approval says the action it wants to take in plain words; the server's own name for it is never shown. */}
      {q.approval && q.detail && q.detail.trim() !== q.question.trim() && <p className="ask-detail">{q.detail}</p>}
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
          <TurnBody run={run} bot={bot} going={going} ask={<Ask run={run} bot={bot} />} />
          {!going && (
            <small className="rmeta" title={stamp(run.created_at)}>
              {ago(run.created_at)}
              {/* A run that never reached Claude (skipped, cancelled before it began) used nothing: no "$0.00" for it. */}
              {run.input_tokens + run.output_tokens > 0 && ` · ${plural(run.input_tokens + run.output_tokens, 'token')} · ${dollars(run.cost_micros)}`}
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
        <div className="ideas" role="group" aria-label="Things to ask">
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

/** One bot's chat: its runs as the conversation, the composer, and its three pills (model, effort, permission mode). */
export function BotChat({ bot, focus, fresh, onSent }: { bot: Bot; focus: string | null; fresh: boolean; onSent: () => void }) {
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
  const effort = bot.effort ?? models.data?.default_effort ?? 'medium';

  const send = (text: string) => start.mutate(text, { onSuccess: onSent });
  // Things to ask it, the bot's own (none when it has none): a click sends one.
  const ideas = [...new Set((bot.examples ?? []).map((t) => t.trim()).filter(Boolean))].slice(0, 6);

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
          `${home.name} is offline: start it, or change where ${bot.name} runs in its settings.`
        ) : update.error ? (
          <span className="err">{update.error.message}</span>
        ) : null
      }
    >
      <SelectChip
        title="Model"
        busy={update.isPending}
        value={bot.model}
        options={models.data?.models.length ? models.data.models.map((m) => ({ value: m.id, label: shortModel(m.name) })) : [{ value: bot.model, label: shortModel(bot.model) || 'Model' }]}
        onPick={(model) => update.mutate({ model })}
      />
      <SelectChip title="Effort" busy={update.isPending} value={effort} options={effortOptions(effort)} onPick={(next) => update.mutate({ effort: next })} />
      <SelectChip
        title="Permission mode"
        busy={update.isPending}
        warn={mode === 'auto'}
        value={mode}
        options={MODES}
        onPick={(permission_mode) => update.mutate({ permission_mode })}
      />
    </Composer>
  );

  return (
    <section className="center" aria-label={`${bot.name}’s chat`}>
      <div className="room-head">
        <div className="solo">
          <b>{bot.name}</b>
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
          sub={bot.summary || 'Say it or type it. It asks you when it is not sure, and learns from your answers.'}
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

const TURN_WORDS: Record<Turn['status'], string> = {
  picking: 'choosing',
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
function PrCard({ turn, run }: { turn: Turn; run: ProjectRun }) {
  const [open, setOpen] = useState(false);
  const answer = useAnswerProjectRun();
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

/** With review at the end: the run's one pull request of it all, merged or rejected here while the run waits on it. */
function WholePr({ run }: { run: ProjectRun }) {
  const answer = useAnswerProjectRun();
  return (
    <section className="prcard open" aria-label="The run’s pull request">
      <div className="prrow">
        <span className="prnum">PR{run.number === null ? '' : ` #${run.number}`}</span>
        <span className="prtitle">Merge the whole run?</span>
        <span className="row">
          <button type="button" className="btn primary sm" disabled={answer.isPending} onClick={() => answer.mutate({ id: run.id, answer: 'merge' })}>
            Merge
          </button>
          <button type="button" className="btn danger sm" disabled={answer.isPending} onClick={() => answer.mutate({ id: run.id, answer: 'reject' })}>
            Reject
          </button>
        </span>
      </div>
      <div className="prbody">
        {run.work_branch && <small className="dim">{run.work_branch}</small>}
        {run.pr_url && (
          <a className="link" href={run.pr_url} target="_blank" rel="noreferrer">
            {run.pr_url}
          </a>
        )}
      </div>
      {answer.error && <div className="err pad">{answer.error.message}</div>}
    </section>
  );
}

/** The orchestrator's own closing turn: no bot, it says the project is done. */
const isClosing = (t: Turn) => t.bot_slug === '' && t.status !== 'picking';

function CrewRun({ run: listed, bots }: { run: ProjectRun; bots: Bot[] }) {
  const live = useProjectRun(runGoing(listed.status) ? listed.id : null);
  const run = live.data?.id === listed.id ? live.data : listed;
  const whole = run.status === 'needs_input' && run.review === 'end' && run.pr_url !== null && !run.turns.some((t) => t.status === 'open');
  const ended = run.status === 'done' ? endedWords(run) : '';
  return (
    <div id={`msg-${run.id}`} className="turnpair">
      <div className="msg me">
        <div className="bubble">{run.task || '(from the instructions)'}</div>
      </div>
      {run.turns.map((t) => {
        if (t.status === 'picking')
          return (
            <div key={t.n} className="note" role="status">
              Choosing who goes next…
            </div>
          );
        const bot = bots.find((b) => b.slug === t.bot_slug);
        const going = t.status === 'running';
        const closing = isClosing(t);
        return (
          <div key={t.n} className="turnpair">
            {t.picked_by === 'orchestrator' && !closing && (
              <div className="note">
                Orchestrator chose {t.bot_name}
                {t.why && ` · ${t.why}`}
              </div>
            )}
            <div id={`msg-${run.id}-${t.n}`} className={`msg bot-msg ${going ? 'live' : ''}`} role="article" aria-label={`${t.bot_name}: turn ${t.n}`}>
              <div className="face">{closing ? <Icon d={ICON.bots} size={20} /> : <BotCat look={bot?.look} mascot={bot?.mascot} size={42} busy={going} />}</div>
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
                {t.said && <Rich text={t.said} />}
                {t.number !== null ? <PrCard turn={t} run={run} /> : t.status === 'unchanged' && !closing && <small className="rmeta">{t.said ? 'no changes' : 'passed · no changes'}</small>}
                {t.error && <div className="err">{t.error}</div>}
              </div>
            </div>
          </div>
        );
      })}
      {whole && <WholePr run={run} />}
      {run.error && <div className="err">{run.error}</div>}
      {ended && <div className="note">{ended}</div>}
    </div>
  );
}

/** Who is in the crew, who is up, and how each turn's pull request went (the strip at the top). */
function Stage({ members, run }: { members: Bot[]; run: ProjectRun | undefined }) {
  const up = run?.turns.find((t) => t.status === 'running')?.bot_slug;
  const turns = run?.turns.filter((t) => t.status !== 'picking') ?? [];
  return (
    <div className="stage">
      <div className="queue" aria-label="The crew">
        {members.map((b) => (
          <div key={b.id} className={`seat ${up === b.slug ? 'up thinking' : ''}`}>
            <BotCat look={b.look} mascot={b.mascot} size={26} busy={up === b.slug} />
            <span>{b.name}</span>
          </div>
        ))}
        {run && runGoing(run.status) && <span className="stage-info">Turn {run.turns.length}</span>}
      </div>
      {run && turns.length > 0 && (
        <div className="turnstrip" aria-label="Turns">
          {turns.map((t) => (
            <button
              key={t.n}
              type="button"
              className={`tchip ${TURN_WORDS[t.status].replace(' ', '-')}`}
              title={t.title || undefined}
              onClick={() => document.getElementById(`msg-${run.id}-${t.n}`)?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })}
            >
              <b>{t.n}</b> {t.bot_name} <small>{t.number !== null ? `#${t.number} ${TURN_WORDS[t.status]}` : isClosing(t) ? 'done' : TURN_WORDS[t.status]}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const CREW_IDEAS = ['Build a one-page site for a product launch', 'Make a tiny browser game with a high score', 'Plan and write a study guide for my next test'];

const OWN = '';

/**
 * The crew's chat: the ticked bots taking turns in the workspace, each turn a pull request. Under the composer the
 * same three pills as a bot's: the model and effort for the next task (each bot's own unless chosen), and when its
 * pull requests wait for the person. Everything else about the crew is in Crew settings.
 */
export function CrewChat({ crew, bots, focus, fresh, onSent }: { crew: Crew; bots: Bot[]; focus: string | null; fresh: boolean; onSent: () => void }) {
  const slug = crew.project?.slug;
  const runs = useProjectRuns(slug);
  const start = useRunProject(slug);
  const cancel = useCancelProjectRun();
  const models = useBotModels();
  const thread = [...(runs.data ?? [])].slice(0, 20).reverse();
  const hero = fresh || !slug || (runs.data !== undefined && thread.length === 0);
  const listed = thread.at(-1);
  // The strip on top follows the run as its turn does: the run itself, read again while a turn is out.
  const live = useProjectRun(listed && runGoing(listed.status) ? listed.id : null);
  const latest = live.data && live.data.id === listed?.id ? live.data : listed;
  const active = thread.findLast((r) => runGoing(r.status));
  const { scroller, onScroll } = useFollow(runs.data, focus);
  const members = bots.filter((b) => crew.members.includes(b.id));
  const failed = start.error ?? crew.error;
  const install = installUrl(failed);
  useNarration(crew.settings.narrate, latest);

  const send = (task: string) => {
    if (slug) start.mutate({ task, model: crew.model, effort: crew.effort }, { onSuccess: onSent });
  };

  const composer = (
    <Composer
      hero={hero}
      focusKey="crew"
      placeholder="Give the crew a task…"
      busy={Boolean(active)}
      sending={start.isPending}
      off={!slug || members.length === 0}
      onSend={send}
      onStop={active ? () => cancel.mutate(active.id) : undefined}
      allowEmpty
      note={
        failed ? (
          <>
            <span className="err">{failed.message}</span>
            {install && (
              <>
                {' '}
                <a href={install} target="_blank" rel="noreferrer">
                  Connect GitHub
                </a>
              </>
            )}
          </>
        ) : !crew.ready ? null : !slug ? (
          'Choose a workspace in the top bar first: the repository and branch the crew works in.'
        ) : members.length === 0 ? (
          'Tick a cat on the crew card to put a bot in the crew.'
        ) : null
      }
    >
      <SelectChip
        title="Model"
        value={crew.model ?? OWN}
        options={[{ value: OWN, label: 'Each bot’s model' }, ...(models.data?.models ?? []).map((m) => ({ value: m.id, label: shortModel(m.name) }))]}
        onPick={(model) => crew.setRun({ model: model || null })}
      />
      <SelectChip
        title="Effort"
        value={crew.effort ?? OWN}
        options={[{ value: OWN, label: 'Each bot’s effort' }, ...EFFORTS]}
        onPick={(effort) => crew.setRun({ effort: (effort || null) as Effort | null })}
      />
      <SelectChip title="Permission mode" wide busy={crew.pending} value={crew.settings.review} options={CREW_MODES} onPick={(review) => crew.save({ settings: { review } })} />
    </Composer>
  );

  return (
    <section className="center" aria-label="The crew’s chat">
      <div className="room-head">
        <Stage members={members} run={hero ? undefined : latest} />
      </div>
      {runs.error && <div className="err pad">{runs.error.message}</div>}
      {hero ? (
        <Hero
          cats={
            <div className="hero-crew">
              {members.map((b) => (
                <span key={b.id}>
                  <BotCat look={b.look} mascot={b.mascot} size={104} mode="full" />
                </span>
              ))}
            </div>
          }
          headline="What are we making?"
          sub="Say it or type it. The crew takes turns, and each turn is a pull request."
          ideas={slug ? CREW_IDEAS : []}
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
