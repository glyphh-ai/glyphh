import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { useBotPlaces, useBotRun, useBotRuns, useCancelRun, useRunBot, working, type Bot } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago, dollars, stamp } from '@/lib/format';
import { Button, EmptyState, LoadingCard, Skeleton } from '@/ui';
import { DecisionLines, decisionsOf, gateNames, WrongDialog } from './ada';
import { QuestionForm, RunChip } from './parts';
import styles from './bots.module.css';
import look from './look.module.css';

/** Where a run ran, by the place's name: `on Acme`; nothing for Glyphh cloud. */
function usePlaceName() {
  const places = useBotPlaces();
  const named = new Map((places.data ?? []).map((p) => [p.id, p]));
  return (id: string | null | undefined) => (id ? (named.get(id) ?? { id, name: 'your machine', mode: 'self' as const, linked: false }) : null);
}

/** One run in full: what it was asked, what each gate decided (corrected in place), the question it waits on, its log. */
function RunDetail({ id, bot }: { id: string; bot: Bot }) {
  const run = useBotRun(id);
  const cancel = useCancelRun();
  const place = usePlaceName();
  const [marking, setMarking] = useState(false);
  if (run.isPending) return <LoadingCard lines={5} />;
  if (run.error) return <ApiErrorNotice error={run.error} />;
  const r = run.data;
  const rest = Object.fromEntries(Object.entries(r.data ?? {}).filter(([k]) => k !== '_gates'));
  const data = Object.keys(rest).length > 0 ? JSON.stringify(rest, null, 2) : '';
  const where = place(r.runs_on);
  return (
    <section className={`${look.panel} ${look.panelBody} ${styles.form}`} aria-label="Run">
      <div className={look.runHead}>
        <span className={look.facts}>
          <RunChip status={r.status} />
          <span className={look.muted} title={stamp(r.created_at)}>
            {ago(r.created_at)}
            {where && ` · on ${where.name}`}
          </span>
        </span>
        <span className={look.muted}>
          {(r.input_tokens + r.output_tokens).toLocaleString('en-GB')} tokens · {dollars(r.cost_micros)} ·{' '}
          {where ? `the Claude key on ${where.name}` : r.own_key ? 'your Claude key' : 'Glyphh’s Claude key'}
        </span>
      </div>
      <div>
        <span className={look.label}>Asked</span>
        <p className={styles.output}>{r.input || '—'}</p>
      </div>
      {decisionsOf(r, bot.spec).length > 0 && (
        <div className={look.tight}>
          <span className={look.label}>What its gates decided</span>
          <DecisionLines run={r} bot={bot} limit={20} />
        </div>
      )}
      {r.status === 'needs_input' && r.question && (
        <div className={look.ask}>
          <QuestionForm run={r} />
        </div>
      )}
      {r.output && (
        <div>
          <span className={look.label}>Result</span>
          <p className={styles.output}>{r.output}</p>
        </div>
      )}
      {r.error && <p className={styles.output}>{r.error}</p>}
      <div>
        <span className={look.label}>Log</span>
        {r.log.length > 0 ? (
          <pre className={styles.log} aria-label="Log">
            {r.log.join('\n')}
          </pre>
        ) : (
          <p className={look.muted}>{working(r.status) ? 'Starting…' : 'Nothing logged.'}</p>
        )}
      </div>
      {data && (
        <div>
          <span className={look.label}>Data</span>
          <pre className={styles.log} aria-label="Data">
            {data}
          </pre>
        </div>
      )}
      <ApiErrorNotice error={cancel.error} />
      <div className={styles.row}>
        {working(r.status) && (
          <Button variant="ghost" icon="close" loading={cancel.isPending} onClick={() => cancel.mutate(r.id)}>
            Cancel run
          </Button>
        )}
        {(r.status === 'done' || r.status === 'failed') && (
          <Button variant="secondary" icon="undo" onClick={() => setMarking(true)}>
            Mark as wrong
          </Button>
        )}
      </div>
      <WrongDialog key={String(marking)} run={r} gates={gateNames(bot)} open={marking} onClose={() => setMarking(false)} />
    </section>
  );
}

/** Run the bot (the app's composer); every run, newest first, with what its gates decided (`?run=` opens one in full). */
export function RunsTab({ bot }: { bot: Bot }) {
  const runs = useBotRuns(bot.slug);
  const start = useRunBot(bot.slug);
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState('');
  const open = (id: string) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p);
        next.set('run', id);
        return next;
      },
      { replace: true },
    );
  const shown = params.get('run') ?? runs.data?.[0]?.id ?? null;
  const place = usePlaceName();
  const home = place(bot.runs_on);

  const run = () =>
    start.mutate(input.trim(), {
      onSuccess: (r) => {
        setInput('');
        open(r.id);
      },
    });

  return (
    <div className={look.columns}>
      <div className={look.stack}>
        <section className={look.section} aria-label="Run it">
          <div className={look.composer}>
            <label htmlFor="bot-input" className={look.label}>
              What to do
            </label>
            <textarea
              id="bot-input"
              rows={2}
              placeholder={`Give ${bot.name} a task…`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && input.trim()) run();
              }}
            />
            <div className={look.runHead}>
              <span className={look.muted}>
                {home
                  ? home.linked
                    ? `It runs on ${home.name}, on the Claude key set there.`
                    : `It runs on ${home.name}, which is offline: start it, or choose Glyphh cloud in Settings, to run the bot.`
                  : 'The bot reads this with its instructions.'}
              </span>
              <Button variant="primary" disabled={input.trim() === ''} loading={start.isPending} onClick={run}>
                Run
              </Button>
            </div>
          </div>
          <ApiErrorNotice error={start.error} />
        </section>
        {shown && <RunDetail key={shown} id={shown} bot={bot} />}
      </div>
      <section className={look.section} aria-label="Decisions">
        <div className={look.labelRow}>
          <h2 className={look.label}>Every run · {runs.data?.length ?? 0}</h2>
        </div>
        <ApiErrorNotice error={runs.error} />
        {runs.isPending && (
          <ul className={`${look.panel} ${look.feed}`} aria-busy="true" aria-label="Loading runs">
            {Array.from({ length: 3 }, (_, i) => (
              <li key={i} aria-hidden="true" className={look.run}>
                <Skeleton height={14} width="60%" />
              </li>
            ))}
          </ul>
        )}
        {runs.data?.length === 0 && (
          <EmptyState icon="logs" title="No runs yet">
            Give the bot something to do and run it.
          </EmptyState>
        )}
        {runs.data && runs.data.length > 0 && (
          <ul className={`${look.panel} ${look.feed}`} aria-label="Runs">
            {runs.data.map((r) => {
              const said = decisionsOf(r, bot.spec)
                .map((d) => `${d.gate} ${d.outcome}`)
                .join(' · ');
              return (
                <li key={r.id}>
                  <button type="button" className={look.runButton} aria-pressed={r.id === shown} onClick={() => open(r.id)}>
                    <span className={look.runHead}>
                      <span className={look.outcome}>{r.input || 'Run'}</span>
                      <RunChip status={r.status} small />
                    </span>
                    {said && <span className={look.by}>{said}</span>}
                    <span className={look.muted} title={stamp(r.created_at)}>
                      {ago(r.created_at)} · {dollars(r.cost_micros)}
                      {r.runs_on && ` · on ${place(r.runs_on)!.name}`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
