import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { runsOnPending, useBotRun, useBotRuns, useCancelRun, useRunBot, useWrongRun, working, type Bot, type BotRun } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago, dollars, stamp } from '@/lib/format';
import { Button, Card, Dialog, EmptyState, ErrorNotice, LoadingCard, Select, Skeleton, TextField, useToast } from '@/ui';
import { COMING } from './ModelPicker';
import { QuestionForm, RunChip, TextArea } from './parts';
import styles from './bots.module.css';

/** Says a finished run (or one item of it) went wrong: what really happened, for the gate that decided to learn. */
function WrongDialog({ run, gates, open, onClose }: { run: BotRun; gates: string[]; open: boolean; onClose: () => void }) {
  const toast = useToast();
  const wrong = useWrongRun();
  const [outcome, setOutcome] = useState('');
  const [gate, setGate] = useState(gates[0] ?? '');
  const [item, setItem] = useState('');
  const send = () =>
    wrong.mutate(
      { id: run.id, outcome: outcome.trim(), gate: gate || undefined, item: item.trim() || undefined },
      {
        onSuccess: (r) => {
          toast.show(`The ${r.gate} gate learned “${r.now}”.`);
          onClose();
        },
      },
    );
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Mark as wrong"
      description="Say what should have happened. The gate that decided learns it, so the next run is right."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={outcome.trim() === ''} loading={wrong.isPending} onClick={send}>
            Correct it
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        <TextField label="What should have happened" value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="leave" />
        {gates.length > 1 && <Select label="Gate" value={gate} onChange={(e) => setGate(e.target.value)} options={gates.map((g) => ({ value: g, label: g }))} />}
        <TextField label="Item (optional)" hint="Its number, for a run that decided many." value={item} onChange={(e) => setItem(e.target.value)} />
        <ApiErrorNotice error={wrong.error} />
      </div>
    </Dialog>
  );
}

/** One run: what it was asked, its log and data, the question it waits on (answered here), cancel and mark wrong. */
function RunDetail({ id, gates }: { id: string; gates: string[] }) {
  const run = useBotRun(id);
  const cancel = useCancelRun();
  const [marking, setMarking] = useState(false);
  if (run.isPending) return <LoadingCard lines={5} />;
  if (run.error) return <ApiErrorNotice error={run.error} />;
  const r = run.data;
  const data = Object.keys(r.data).length > 0 ? JSON.stringify(r.data, null, 2) : '';
  return (
    <Card>
      <section className={styles.form} aria-label="Run">
        <div className={styles.spread}>
          <span className={styles.row}>
            <RunChip status={r.status} />
            <span className={styles.muted} title={stamp(r.created_at)}>
              {ago(r.created_at)}
            </span>
          </span>
          <span className={styles.muted}>
            {(r.input_tokens + r.output_tokens).toLocaleString('en-GB')} tokens · {dollars(r.cost_micros)} · {r.own_key ? 'your Claude key' : 'Glyphh’s Claude key'}
          </span>
        </div>
        <div>
          <span className={styles.label}>Asked</span>
          <p className={styles.output}>{r.input || '—'}</p>
        </div>
        {r.status === 'needs_input' && r.question && (
          <div className={styles.waiting}>
            <QuestionForm run={r} />
          </div>
        )}
        <div>
          <span className={styles.label}>Log</span>
          {r.log.length > 0 ? (
            <pre className={styles.log} aria-label="Log">
              {r.log.join('\n')}
            </pre>
          ) : (
            <p className={styles.muted}>{working(r.status) ? 'Starting…' : 'Nothing logged.'}</p>
          )}
        </div>
        {data && (
          <div>
            <span className={styles.label}>Data</span>
            <pre className={styles.log} aria-label="Data">
              {data}
            </pre>
          </div>
        )}
        {r.output && (
          <div>
            <span className={styles.label}>Result</span>
            <p className={styles.output}>{r.output}</p>
          </div>
        )}
        {r.error && <p className={styles.output}>{r.error}</p>}
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
      </section>
      <WrongDialog key={String(marking)} run={r} gates={gates} open={marking} onClose={() => setMarking(false)} />
    </Card>
  );
}

/** Run the bot with an input; its runs, newest first (`?run=` opens one); the open run in full. */
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
  const gates = bot.gate_models.map((g) => g.replace(`${bot.slug}-`, ''));

  const run = () =>
    start.mutate(input.trim(), {
      onSuccess: (r) => {
        setInput('');
        open(r.id);
      },
    });

  return (
    <div className={styles.stack}>
      <Card>
        <div className={styles.form}>
          <TextArea label="What to do" hint="The bot reads this with its instructions." value={input} onChange={(e) => setInput(e.target.value)} />
          {bot.runs_on && !start.error && <span className={styles.muted}>{COMING}</span>}
          {runsOnPending(start.error) ? <ErrorNotice message={COMING} /> : <ApiErrorNotice error={start.error} />}
          <div className={styles.row}>
            <Button variant="primary" disabled={input.trim() === ''} loading={start.isPending} onClick={run}>
              Run
            </Button>
          </div>
        </div>
      </Card>
      <ApiErrorNotice error={runs.error} />
      {runs.isPending && (
        <ul className={styles.steps} aria-busy="true" aria-label="Loading runs">
          {Array.from({ length: 3 }, (_, i) => (
            <li key={i} aria-hidden="true" className={styles.runRow}>
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
        <ul className={styles.steps} aria-label="Runs">
          {runs.data.map((r) => (
            <li key={r.id}>
              <button type="button" className={styles.runRow} aria-pressed={r.id === shown} onClick={() => open(r.id)}>
                <span className={styles.spread}>
                  <span className={styles.grow}>{r.input || 'Run'}</span>
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
      {shown && <RunDetail key={shown} id={shown} gates={gates} />}
    </div>
  );
}
