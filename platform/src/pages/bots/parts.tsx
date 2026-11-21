import { useId, useState, type TextareaHTMLAttributes } from 'react';
import { Link } from 'react-router';
import { useAnswerRun, useCancelRun, type Answer, type BotRun, type BotSpec, type RunStatus } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import { randomLook, type Look } from '@/bots/cat/look';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ago, dollars, stamp } from '@/lib/format';
import { Button, Chip, type ChipTone } from '@/ui';
import styles from './bots.module.css';

export const botPath = (slug: string) => `/bots/${encodeURIComponent(slug)}`;

/** A tool's key as words: gmail-send-email is "Send email" (of Gmail). */
export const toolWords = (key: string) => {
  const words = key.split(/[-_]/).slice(1).join(' ');
  return words ? words[0]!.toUpperCase() + words.slice(1) : key;
};

/** The loop's steps, one a line, as the spec names them. */
export function LoopSteps({ spec }: { spec: BotSpec }) {
  const steps = Array.isArray(spec.loop) ? spec.loop : [];
  if (steps.length === 0) return <p className={styles.muted}>No steps yet.</p>;
  return (
    <ol className={styles.steps} aria-label="Steps">
      {steps.map((s, i) => {
        const name = String(s.step ?? s.name ?? `Step ${i + 1}`);
        const what = [s.tool && `uses ${toolWords(String(s.tool))}`, s.gate && `gate ${String(s.gate)}`, s.ask && 'waits for your approval']
          .filter(Boolean)
          .join(' · ');
        return (
          <li key={i} className={styles.step}>
            <span className={styles.toolName}>
              {i + 1}. {name}
            </span>
            {what && <span className={styles.muted}> · {what}</span>}
          </li>
        );
      })}
    </ol>
  );
}

/** A bot's cat on its ink tile. */
export function CatTile({ look, size = 56, busy, label }: { look: Look | null | undefined; size?: number; busy?: boolean; label?: string }) {
  return (
    <span className={styles.catTile}>
      <Cat look={look} size={size} busy={busy} label={label} />
    </span>
  );
}

/** The cat, with Shuffle for another. */
export function CatPicker({ look, onChange }: { look: Look; onChange: (look: Look) => void }) {
  return (
    <div className={styles.row}>
      <CatTile look={look} size={72} label="The bot's cat" />
      <Button variant="secondary" size="sm" onClick={() => onChange(randomLook())}>
        Shuffle
      </Button>
    </div>
  );
}

const tones: Record<RunStatus, ChipTone> = { queued: 'neutral', running: 'blue', needs_input: 'amber', done: 'green', failed: 'red', skipped: 'neutral' };
const words: Record<RunStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  needs_input: 'Needs you',
  done: 'Done',
  failed: 'Failed',
  skipped: 'Cancelled',
};

export function RunChip({ status }: { status: RunStatus }) {
  return <Chip tone={tones[status]}>{words[status]}</Chip>;
}

type AreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; hint?: string; mono?: boolean };

/** A labelled text area, as TextField is for one line. */
export function TextArea({ label, hint, id, mono, className, ...rest }: AreaProps) {
  const own = useId();
  const fieldId = id ?? own;
  return (
    <div className={styles.field}>
      <label htmlFor={fieldId} className={styles.label}>
        {label}
      </label>
      <textarea id={fieldId} className={`${styles.textarea} ${mono ? styles.mono : ''} ${className ?? ''}`} spellCheck={mono ? false : undefined} {...rest} />
      {hint && <span className={styles.muted}>{hint}</span>}
    </div>
  );
}

/** A title, with the count beside it, for a section of a detail page. */
export function SectionTitle({ children, count }: { children: string; count?: number }) {
  return (
    <h2 className={styles.sectionTitle}>
      {children}
      {count !== undefined && <span className={styles.muted}> {count}</span>}
    </h2>
  );
}

/**
 * A run's question, answered here: one option per button, or for a batch each item's own option (all of them at
 * once with "All:"), sent together. Cancel stops the run instead.
 */
export function QuestionForm({ run, onDone }: { run: BotRun; onDone?: (r: BotRun) => void }) {
  const answer = useAnswerRun();
  const cancel = useCancelRun();
  const q = run.question;
  const [picked, setPicked] = useState<Record<string, string>>({});
  if (!q) return null;
  const batch = q.batch ?? [];
  const send = (a: Answer) => answer.mutate({ id: run.id, answer: a }, { onSuccess: onDone });
  const ready = batch.length > 0 && batch.every((item) => picked[String(item.n)]);
  const all = (option: string) => setPicked(Object.fromEntries(batch.map((item) => [String(item.n), option])));
  const busy = answer.isPending || cancel.isPending;

  return (
    <section className={styles.question} aria-label="Question">
      <p className={styles.questionText}>{q.question}</p>
      {batch.length === 0 ? (
        <div className={styles.row}>
          {q.options.map((option) => (
            <Button key={option} variant="secondary" disabled={busy} loading={answer.isPending && answer.variables?.answer === option} onClick={() => send(option)}>
              {option}
            </Button>
          ))}
        </div>
      ) : (
        <>
          <div className={styles.row}>
            <span className={styles.muted}>All:</span>
            {q.options.map((option) => (
              <Button key={option} size="sm" variant="ghost" disabled={busy} onClick={() => all(option)}>
                {option}
              </Button>
            ))}
          </div>
          <ol className={styles.batch} aria-label="Items">
            {batch.map((item) => {
              const key = String(item.n);
              return (
                <li key={key} className={styles.batchItem}>
                  <span className={styles.grow}>
                    <span className={styles.muted}>{item.n}.</span> {item.label}
                  </span>
                  <span className={styles.segmented} role="radiogroup" aria-label={item.label}>
                    {q.options.map((option) => (
                      <button
                        key={option}
                        type="button"
                        role="radio"
                        aria-checked={picked[key] === option}
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
          <div className={styles.row}>
            <Button variant="primary" disabled={!ready || busy} loading={answer.isPending} onClick={() => send(picked)}>
              Send answers
            </Button>
            {!ready && <span className={styles.muted}>Choose for every item, or use All.</span>}
          </div>
        </>
      )}
      <div className={styles.row}>
        <Button variant="ghost" size="sm" icon="close" disabled={busy} loading={cancel.isPending} onClick={() => cancel.mutate(run.id, { onSuccess: onDone })}>
          Cancel run
        </Button>
      </div>
      <ApiErrorNotice error={answer.error ?? cancel.error} />
    </section>
  );
}

/** One waiting run, as the approvals queue and a bot's runs list it: whose, when, what it asks, answered in place. */
export function WaitingRun({ run, botName, showBot = true }: { run: BotRun; botName?: string; showBot?: boolean }) {
  return (
    <article className={styles.waiting} aria-label={`${botName ?? run.bot_slug}: ${run.question?.question ?? 'waiting'}`}>
      <div className={styles.spread}>
        <span className={styles.row}>
          {showBot && (
            <Link to={`${botPath(run.bot_slug)}?tab=runs&run=${encodeURIComponent(run.id)}`} className={styles.botLink}>
              {botName ?? run.bot_slug}
            </Link>
          )}
          <span className={styles.muted} title={stamp(run.created_at)}>
            {run.input ? `“${run.input}” · ` : ''}
            {ago(run.created_at)}
          </span>
        </span>
        <span className={styles.muted}>{dollars(run.cost_micros)} so far</span>
      </div>
      <QuestionForm run={run} />
    </article>
  );
}
