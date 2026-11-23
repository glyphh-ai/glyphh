// The run being followed, under the canvas: its state and the step it is at (lit on the canvas too), what it asks and
// the answer (an option's button, or your own words), Cancel, and its trail: who started it (a person, the schedule,
// Claude), each step with the bot that did it, each question and who answered.
import { useEffect, useState } from 'react';
import type { Bot } from '@/api/bots';
import { live, questionOf, useAnswerProgramRun, useCancelProgramRun, useProgramEvents, type Program, type ProgramEvent, type ProgramRun } from '@/api/programs';
import { ago } from '@/lib/format';
import { BotCat } from '../shell/bits';
import { eventWords, runWords, stepTitle, whoMark, whoWords } from './words';

const clock = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString('en-GB');
};

function Who({ by }: { by: string | null }) {
  const mark = whoMark(by);
  const title = whoWords(by);
  if (mark === 'schedule')
    return (
      <span className="pwho" title="The schedule" aria-label="The schedule">
        ◷
      </span>
    );
  if (mark === 'connector')
    return (
      <span className="pwho" title="Claude" aria-label="Claude">
        ✳
      </span>
    );
  return (
    <span className="pwho person" title={title} aria-label={title}>
      {(by ?? 'y').charAt(0).toUpperCase()}
    </span>
  );
}

function Line({ e, bots }: { e: ProgramEvent; bots: Bot[] }) {
  const bot = e.bot ? bots.find((b) => b.slug === e.bot) : undefined;
  const loud = e.kind === 'asked' || e.kind === 'failed' || e.ok === false;
  return (
    <li className={`pev k-${e.kind}${loud ? ' loud' : ''}`}>
      <time dateTime={e.at}>{clock(e.at)}</time>
      {e.kind === 'step' ? (
        <span className="pev-bot" title={bot ? `${bot.name} did it` : undefined}>
          {bot ? <BotCat look={bot.look} mascot={bot.mascot} size={18} /> : <i className="sn-nocat" />}
          <b>{bot?.name ?? 'Its bot'}</b>
        </span>
      ) : e.kind === 'started' || e.kind === 'answered' || e.kind === 'cancelled' ? (
        <Who by={e.by} />
      ) : (
        <span className="pwho dot" aria-hidden />
      )}
      <span className="pev-text">{eventWords(e)}</span>
      {e.kind === 'step' && <span className={e.ok === false ? 'pev-ok bad' : 'pev-ok'}>{e.ok === false ? 'failed' : 'ok'}</span>}
    </li>
  );
}

export function RunPanel({ program, run, bots, open, onToggle }: { program: Program; run: ProgramRun; bots: Bot[]; open: boolean; onToggle: () => void }) {
  const following = live(run.status);
  const events = useProgramEvents(run.id, following);
  // Once the run is over, its last lines are read once more (the end may have come between two reads).
  const { refetch } = events;
  useEffect(() => {
    void refetch();
  }, [run.status, refetch]);
  const answer = useAnswerProgramRun();
  const cancel = useCancelProgramRun();
  const [words, setWords] = useState('');
  const q = run.status === 'needs_input' ? questionOf(run) : null;
  const at = run.at ? program.flow.find((s) => s.id === run.at) : undefined;
  const reply = (text: string) => {
    if (!text.trim()) return;
    answer.mutate({ id: run.id, answer: text.trim() }, { onSuccess: () => setWords('') });
  };

  return (
    <section className={`prun ${open ? 'open' : ''} s-${run.status}`} aria-label="The run">
      <div className="prun-head">
        <button type="button" className="prun-fold" aria-expanded={open} aria-label={open ? 'Fold the run away' : 'Show the run'} onClick={onToggle}>
          {open ? '▾' : '▴'}
        </button>
        <span className={`pstatus s-${run.status}`} role="status">
          <i />
          {runWords(run.status)}
        </span>
        {at && following && (
          <span className="prun-at">
            at <b>{stepTitle(at)}</b>
          </span>
        )}
        <span className="prun-meta">
          Started by {whoWords(null, run.trigger)} · {ago(run.created_at)}
          {run.input ? ` · given “${run.input.length > 40 ? `${run.input.slice(0, 39)}…` : run.input}”` : ''}
        </span>
        <span className="spacer" />
        {following && (
          <button type="button" className="btn ghost tiny" disabled={cancel.isPending} onClick={() => cancel.mutate(run.id)}>
            {cancel.isPending ? 'Cancelling…' : 'Cancel run'}
          </button>
        )}
      </div>
      {open && (
        <div className="prun-body">
          {q && (
            <div className="pask" role="group" aria-label="It asks you">
              <p className="ask-q">{q.question}</p>
              {q.detail && <p className="dim">{q.detail}</p>}
              {q.options && q.options.length > 0 ? (
                <div className="row wrap">
                  {q.options.map((o) => (
                    <button key={o} type="button" className="btn" disabled={answer.isPending} onClick={() => reply(o)}>
                      {o}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="row">
                  <input aria-label="Your answer" placeholder="Your answer" value={words} onChange={(e) => setWords(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && reply(words)} />
                  <button type="button" className="btn primary" disabled={answer.isPending || !words.trim()} onClick={() => reply(words)}>
                    Answer
                  </button>
                </div>
              )}
              {answer.error && <small className="err">{answer.error.message}</small>}
            </div>
          )}
          {run.status === 'failed' && run.error && <div className="err pad">{run.error}</div>}
          {cancel.error && <div className="err pad">{cancel.error.message}</div>}
          <ol className="pevents" aria-label="What happened">
            {(events.data ?? []).map((e) => (
              <Line key={e.n} e={e} bots={bots} />
            ))}
            {events.isPending && <li className="dim">Reading what happened…</li>}
            {following && <li className="pev waiting">{run.status === 'needs_input' ? 'Waiting for your answer' : 'Working…'}</li>}
          </ol>
        </div>
      )}
    </section>
  );
}
