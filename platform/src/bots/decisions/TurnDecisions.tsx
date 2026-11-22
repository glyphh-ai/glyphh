import { useState, type ReactNode } from 'react';
import { useConfirm, useDecisions, useRelabel, type Decision } from '@/api/botDecisions';
import { others, pct, whoWords } from './words';

/** Who decided, as a turn's row says it: Ada with how sure she was, you, or the gate's default. */
export const byLine = (d: Decision) => (d.who === 'ada' && d.confidence !== null ? `Ada · ${pct(d.confidence)} sure` : whoWords[d.who]);

/**
 * One decision in a chat turn, in the Glyphh Bot app's look: the item, its gate, the outcome (corrected: what it is
 * now, what it said struck through), who decided, and Right or Wrong once the run is over. Right keeps it as a
 * precedent of the gate (`/confirm`); Wrong says what it should have been (one other outcome: that one; several: a
 * pill each) and the gate learns it (`/relabel`). Both go through the gate's Ada model on the server.
 */
export function TurnDecisionRow({ slug, decision: d, over, gates }: { slug: string; decision: Decision; over: boolean; gates: number }) {
  const confirm = useConfirm(slug);
  const relabel = useRelabel(slug);
  const [fixing, setFixing] = useState(false);
  const busy = confirm.isPending || relabel.isPending;
  const fixed = d.corrected !== null && d.corrected !== d.outcome;
  const options = others(d);
  const wrong = (outcome: string) => relabel.mutate({ ids: [d.id], outcome }, { onSuccess: () => setFixing(false) });
  const error = confirm.error ?? relabel.error;
  return (
    <div className={`drow ${fixed ? 'fixed' : d.confirmed ? 'right' : 'open'}`} role="row" aria-label={`${d.label}: ${d.now ?? '—'}`}>
      <span className="dlabel" title={d.label}>
        {gates > 1 && <i>{d.gate}</i>}
        {d.label}
      </span>
      <span className="dout" title={fixed ? `Corrected from ${d.outcome}` : undefined}>
        {d.now ?? '—'}
      </span>
      <span className="dby">{fixed ? 'You' : byLine(d)}</span>
      <span className="dact">
        {!over ? null : fixed ? (
          <small>Ada learned it</small>
        ) : d.confirmed ? (
          <small>Kept</small>
        ) : fixing ? (
          <>
            {options.map((o) => (
              <button key={o} type="button" className="pill" disabled={busy} onClick={() => wrong(o)}>
                {o}
              </button>
            ))}
            <button type="button" className="pill" aria-label="Never mind" onClick={() => setFixing(false)}>
              ×
            </button>
          </>
        ) : (
          <>
            <button type="button" className="pill" aria-label={`Right: ${d.label}`} disabled={busy} onClick={() => confirm.mutate([d.id])}>
              Right
            </button>
            <button
              type="button"
              className="pill"
              aria-label={`Wrong: ${d.label}`}
              disabled={busy || options.length === 0}
              onClick={() => (options.length === 1 ? wrong(options[0]!) : setFixing(true))}
            >
              Wrong
            </button>
          </>
        )}
      </span>
      {error && <span className="err">{error.message}</span>}
    </div>
  );
}

/**
 * A run's decisions inside the bot's turn, as the server keeps them (readable labels, never raw JSON), each trainable
 * in place. Until the server has any for the run (it copies them after each step of the run), `fallback` shows what
 * the run's own data says.
 */
export function TurnDecisions({ slug, runId, over, fallback }: { slug: string; runId: string; over: boolean; fallback?: ReactNode }) {
  const page = useDecisions(slug, { run_id: runId, sort: 'time', order: 'asc', limit: 100 }, over ? undefined : 3000);
  const rows = page.data?.decisions ?? [];
  if (rows.length === 0) return <>{fallback ?? null}</>;
  const gates = Object.keys(page.data?.gates ?? {}).length;
  return (
    <div className="dtable" role="table" aria-label="Decisions">
      <div className="dhead2">
        <span>Ada decided</span>
        <span>{page.data!.total}</span>
      </div>
      {rows.map((d) => (
        <TurnDecisionRow key={d.id} slug={slug} decision={d} over={over} gates={gates} />
      ))}
    </div>
  );
}
