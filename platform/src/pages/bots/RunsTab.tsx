import { useState } from 'react';
import { useBotRun, useBotRuns, useRunBot, type Bot, type RunStep } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago, dollars, stamp } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard } from '@/ui';
import { RunChip, TextArea } from './parts';
import styles from './bots.module.css';

const show = (value: unknown) => (typeof value === 'string' ? value : JSON.stringify(value, null, 2));
const kinds: Record<RunStep['kind'], string> = { text: 'Said', tool: 'Tool', ada: 'Ada' };

function Step({ step }: { step: RunStep }) {
  return (
    <li className={`${styles.step} ${step.is_error ? styles.stepError : ''}`}>
      <span className={styles.toolName}>
        {kinds[step.kind]}
        {step.name ? ` · ${step.name}` : ''}
      </span>
      {step.is_error && <span className={styles.muted}> · failed</span>}
      {step.input != null && step.kind !== 'text' && <pre className={styles.pre}>{show(step.input)}</pre>}
      {step.output != null && <pre className={styles.pre}>{show(step.output)}</pre>}
    </li>
  );
}

/** One run, asked for again every two seconds until it is done or failed. */
function RunDetail({ id }: { id: string }) {
  const run = useBotRun(id);
  if (run.isPending) return <LoadingCard />;
  if (run.error) return <ApiErrorNotice error={run.error} />;
  const r = run.data;
  return (
    <Card>
      <section className={styles.form} aria-label="Run">
        <div className={styles.spread}>
          <RunChip status={r.status} />
          <span className={styles.muted}>
            {(r.input_tokens + r.output_tokens).toLocaleString('en-GB')} tokens · {dollars(r.cost_micros)}
          </span>
        </div>
        <div>
          <span className={styles.label}>Asked</span>
          <p className={styles.output}>{r.input}</p>
        </div>
        {r.steps.length > 0 && (
          <div>
            <span className={styles.label}>Steps</span>
            <ol className={styles.steps}>
              {r.steps.map((step, i) => (
                <Step key={i} step={step} />
              ))}
            </ol>
          </div>
        )}
        {r.output && (
          <div>
            <span className={styles.label}>Answer</span>
            <p className={styles.output}>{r.output}</p>
          </div>
        )}
        {r.error && <p className={styles.output}>{r.error}</p>}
        {(r.status === 'queued' || r.status === 'running') && <p className={styles.muted}>Working…</p>}
      </section>
    </Card>
  );
}

/** Run the bot with an input; its runs, newest first; one run's steps, answer, tokens and cost. */
export function RunsTab({ bot }: { bot: Bot }) {
  const runs = useBotRuns(bot.slug);
  const start = useRunBot(bot.slug);
  const [input, setInput] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const shown = open ?? runs.data?.[0]?.id ?? null;

  const run = () =>
    start.mutate(input.trim(), {
      onSuccess: (r) => {
        setInput('');
        setOpen(r.id);
      },
    });

  return (
    <div className={styles.stack}>
      <Card>
        <div className={styles.form}>
          <TextArea label="What to do" hint="The bot reads this with its instructions." value={input} onChange={(e) => setInput(e.target.value)} />
          <ApiErrorNotice error={start.error} />
          <div className={styles.row}>
            <Button variant="primary" disabled={input.trim() === ''} loading={start.isPending} onClick={run}>
              Run
            </Button>
          </div>
        </div>
      </Card>
      {runs.isPending && <LoadingCard />}
      <ApiErrorNotice error={runs.error} />
      {runs.data?.length === 0 && (
        <EmptyState icon="logs" title="No runs yet">
          Give the bot something to do and run it.
        </EmptyState>
      )}
      {runs.data && runs.data.length > 0 && (
        <ul className={styles.steps} aria-label="Runs">
          {runs.data.map((r) => (
            <li key={r.id}>
              <button type="button" className={styles.runRow} aria-pressed={r.id === shown} onClick={() => setOpen(r.id)}>
                <span className={styles.spread}>
                  <span className={styles.grow}>{r.input}</span>
                  <RunChip status={r.status} />
                </span>
                <span className={styles.muted} title={stamp(r.created_at)}>
                  {ago(r.created_at)} · {dollars(r.cost_micros)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {shown && <RunDetail key={shown} id={shown} />}
    </div>
  );
}
