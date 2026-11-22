import { useState } from 'react';
import { useBotGates, useWrongRun, type Bot, type BotRun } from '@/api/bots';
import { ago, stamp } from '@/lib/format';
import { byWords, decisionsOf, outcomesOf } from '../ada';

/**
 * A run's decisions as its own data has them, for a turn whose decisions the server has not copied yet (the chat
 * shows the server's, src/bots/decisions/TurnDecisions, once it has): what was decided on, the outcome, who decided,
 * and Right or Wrong. Wrong says what it should have been, and the gate learns it in Ada
 * (`POST /v1/bot-runs/{id}/wrong`). Right keeps the row as it is here.
 */
export type Row = { run: BotRun; gate: string; item?: number; label: string; outcome: string; by: string; p?: number | null; /** A gate over many items whose items the run did not keep: its count, not one decision to correct. */ sum?: string };

/** A run's decisions, one row each: an item of a gate over many, or the gate's one decision. */
export function rowsOf(run: BotRun, bot: Bot): Row[] {
  return decisionsOf(run, bot.spec).flatMap((d): Row[] =>
    d.items.length
      ? d.items.map((it) => ({ run, gate: d.gate, item: it.n, label: it.label, outcome: it.outcome, by: it.by, p: it.p }))
      : [{ run, gate: d.gate, label: d.gate, outcome: d.outcome, by: d.by, p: d.p, sum: d.each ? `Ada ${d.decided ?? 0} · you ${d.asked ?? 0}` : undefined }],
  );
}

const key = (r: Row) => `${r.run.id}:${r.gate}:${r.item ?? ''}`;

/** One decision: its label, outcome, who decided, and Right or Wrong (once its run is over). */
export function DecisionRow({ row, bot, when }: { row: Row; bot: Bot; when?: boolean }) {
  const wrong = useWrongRun();
  const stats = useBotGates(bot.slug);
  const [state, setState] = useState<'open' | 'right' | 'fixing'>('open');
  const [other, setOther] = useState('');
  const [now, setNow] = useState<string | null>(null);
  const over = !row.sum && (row.run.status === 'done' || row.run.status === 'failed');
  const options = outcomesOf(bot.spec, row.gate, stats.data?.[row.gate]).filter((o) => o !== row.outcome);
  const send = (outcome: string) =>
    wrong.mutate(
      { id: row.run.id, outcome, gate: row.gate, item: row.item === undefined ? undefined : String(row.item) },
      { onSuccess: (r) => setNow(r.now) },
    );
  const what = row.item === undefined ? row.gate : `${row.gate} item ${row.item}`;

  return (
    <div className={`drow ${now ? 'fixed' : state}`} role="row" aria-label={`${row.label}: ${now ?? row.outcome}`}>
      {when && (
        <span className="dwhen" title={stamp(row.run.created_at)}>
          {ago(row.run.created_at)}
        </span>
      )}
      <span className="dlabel">
        {row.item !== undefined && <i>{row.item}</i>}
        {row.label}
      </span>
      <span className="dout">{now ?? row.outcome}</span>
      <span className="dby">{now ? 'You' : (row.sum ?? byWords(row))}</span>
      <span className="dact">
        {now ? (
          <small>Ada learned it</small>
        ) : !over ? null : state === 'right' ? (
          <small>Kept</small>
        ) : state === 'fixing' ? (
          <>
            {options.map((o) => (
              <button key={o} type="button" className="pill" disabled={wrong.isPending} onClick={() => send(o)}>
                {o}
              </button>
            ))}
            {options.length === 0 && (
              <>
                <input aria-label={`What ${what} should have been`} placeholder="Should have been…" value={other} onChange={(e) => setOther(e.target.value)} />
                <button type="button" className="pill on" disabled={!other.trim() || wrong.isPending} onClick={() => send(other.trim())}>
                  Send
                </button>
              </>
            )}
            <button type="button" className="pill" aria-label="Never mind" onClick={() => setState('open')}>
              ×
            </button>
          </>
        ) : (
          <>
            <button type="button" className="pill" aria-label={`Right: ${what}`} onClick={() => setState('right')}>
              Right
            </button>
            <button type="button" className="pill" aria-label={`Wrong: ${what}`} onClick={() => (options.length === 1 ? send(options[0]!) : setState('fixing'))}>
              Wrong
            </button>
          </>
        )}
      </span>
      {wrong.error && <span className="err">{wrong.error.message}</span>}
    </div>
  );
}

/** A run's decisions inside the bot's turn. */
export function RunDecisions({ run, bot }: { run: BotRun; bot: Bot }) {
  const rows = rowsOf(run, bot);
  if (rows.length === 0) return null;
  return (
    <div className="dtable" role="table" aria-label="Decisions">
      <div className="dhead2">
        <span>Ada decided</span>
        <span>{rows.length}</span>
      </div>
      {rows.map((r) => (
        <DecisionRow key={key(r)} row={r} bot={bot} />
      ))}
    </div>
  );
}
