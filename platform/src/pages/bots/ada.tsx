import { useState } from 'react';
import { Link } from 'react-router';
import { useBotPlaces, useWrongRun, type Bot, type BotRun, type BotSpec, type GateDecision, type GateStat, type ItemDecision } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { plural } from '@/lib/format';
import { Button, Dialog, Select, TextField, useToast } from '@/ui';
import { botPath, toolWords } from './parts';
import styles from './bots.module.css';
import look from './look.module.css';

/**
 * What makes a Glyphh bot, in the Glyphh Bot app's look: its gates in Ada (what each decides, its precedents, how
 * often it asks you and how often it was right), the decisions its runs made (who made each, corrected in place),
 * what it watches, and the tools the person's Glyphh connection gives Claude for it.
 */

/** The gates' names: the bot's gate models are `<slug>-<gate>`. */
export const gateNames = (bot: Bot) => bot.gate_models.map((g) => g.replace(`${bot.slug}-`, ''));

/** 0.18 as `18%`; nothing known as `—`. */
export const pct = (rate: number | null | undefined) => (rate === null || rate === undefined ? '—' : `${Math.round(rate * 100)}%`);

/** Who decided: Ada from her precedents (with her confidence), the person, or the gate's default. */
export function byWords(d: { by: string; p?: number | null }) {
  if (d.by === 'ada') return d.p ? `Ada · ${pct(d.p)} sure` : 'Ada';
  if (d.by === 'person') return 'You';
  if (d.by === 'default') return 'Default';
  if (d.by === 'deferred') return 'Next run';
  return d.by;
}

/** A gate's outcomes as its spec names them (`outcomes`, or `options` in older specs). */
export function outcomesOf(spec: BotSpec, gate: string, stat?: GateStat): string[] {
  if (stat?.outcomes?.length) return stat.outcomes;
  const g = (spec.gates ?? {})[gate] as { outcomes?: unknown; options?: unknown } | undefined;
  const list = g?.outcomes ?? g?.options;
  return Array.isArray(list) ? list.map(String) : [];
}

export type RunDecision = GateDecision & { gate: string; items: ItemDecision[] };

/**
 * The decisions one run made, gate by gate (`run.data._gates`), each with the items of a gate over many items
 * (`run.data[step].decisions`, the step the gate sits on in the loop).
 */
export function decisionsOf(run: BotRun, spec: BotSpec): RunDecision[] {
  const gates = (run.data?._gates ?? {}) as Record<string, GateDecision>;
  const steps = Array.isArray(spec.loop) ? spec.loop : [];
  return Object.entries(gates).map(([gate, d]) => {
    const step = steps.find((s) => s.gate === gate);
    const keys = [step?.id, step?.step, gate].filter((k): k is string => typeof k === 'string');
    const held = keys.map((k) => run.data?.[k] as { decisions?: unknown } | undefined).find((v) => Array.isArray(v?.decisions));
    return { ...d, gate, items: d.each && held ? (held.decisions as ItemDecision[]) : [] };
  });
}

/** Says a decision (a run's, or one item of it) was wrong: what should have happened, learned by its gate in Ada. */
export function WrongDialog({
  run,
  gates,
  open,
  onClose,
  gate: given,
  item: givenItem,
}: {
  run: BotRun;
  gates: string[];
  open: boolean;
  onClose: () => void;
  gate?: string;
  item?: number;
}) {
  const toast = useToast();
  const wrong = useWrongRun();
  const [outcome, setOutcome] = useState('');
  const [gate, setGate] = useState(given ?? gates[0] ?? '');
  const [item, setItem] = useState(givenItem === undefined ? '' : String(givenItem));
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
      description="Say what should have happened. The gate that decided learns it in Ada, so the next run is right."
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

/** A run's decisions, one line a gate (and under a gate over many items, one line an item), each correctable. */
export function DecisionLines({ run, bot, limit = 6 }: { run: BotRun; bot: Bot; limit?: number }) {
  const found = decisionsOf(run, bot.spec);
  const [fixing, setFixing] = useState<{ gate: string; item?: number } | null>(null);
  const finished = run.status === 'done' || run.status === 'failed';
  if (found.length === 0) return null;
  return (
    <>
      <ul className={look.decisions} aria-label="Decisions">
        {found.map((d) => (
          <li key={d.gate}>
            <div className={look.decision} aria-label={`${d.gate}: ${d.outcome}`}>
              <span className={look.gateName}>{d.gate}</span>
              <span className={look.outcome}>{d.outcome}</span>
              <span className={look.by}>{d.each ? `Ada ${d.decided ?? 0} · you ${d.asked ?? 0}` : byWords(d)}</span>
              {finished && !d.each ? (
                <button type="button" className={look.wrong} onClick={() => setFixing({ gate: d.gate })} aria-label={`Wrong? ${d.gate}`}>
                  Wrong?
                </button>
              ) : (
                <span />
              )}
            </div>
            {d.items.length > 0 && (
              <ul className={`${look.decisions} ${look.items}`} aria-label={`${d.gate} items`}>
                {d.items.slice(0, limit).map((it) => (
                  <li key={it.n} className={`${look.decision} ${look.itemLine}`}>
                    <span className={look.itemLabel}>
                      {it.n}. {it.label}
                    </span>
                    <span className={look.outcome}>{it.outcome}</span>
                    <span className={look.by}>{byWords(it)}</span>
                    {finished ? (
                      <button type="button" className={look.wrong} onClick={() => setFixing({ gate: d.gate, item: it.n })} aria-label={`Wrong? ${d.gate} item ${it.n}`}>
                        Wrong?
                      </button>
                    ) : (
                      <span />
                    )}
                  </li>
                ))}
                {d.items.length > limit && <li className={look.muted}>and {d.items.length - limit} more</li>}
              </ul>
            )}
          </li>
        ))}
      </ul>
      {fixing && <WrongDialog run={run} gates={gateNames(bot)} gate={fixing.gate} item={fixing.item} open onClose={() => setFixing(null)} />}
    </>
  );
}

/** One gate's numbers from Ada: precedents, who decided, how often it asks, how often it was right when it asked. */
export function GateCard({ bot, name, stat, compact }: { bot: Bot; name: string; stat: GateStat; compact?: boolean }) {
  const outcomes = outcomesOf(bot.spec, name, stat);
  const d = stat.decisions;
  const agree = stat.agreement;
  const total = d ? Math.max(1, d.total) : 1;
  const body = (
    <>
      <div className={look.gateTop}>
        <div>
          <h3 className={look.gateName}>{name}</h3>
          {outcomes.length > 0 && (
            <div className={look.outcomes} aria-label="Outcomes">
              {outcomes.map((o) => (
                <span key={o} className={`${look.pill} ${look.pillSmall}`}>
                  {o}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className={look.big}>
          <span className={look.bigNumber}>{(stat.precedents ?? 0).toLocaleString('en-GB')}</span>
          <span className={look.label}>precedents</span>
        </div>
      </div>
      {d && d.total > 0 && (
        <div className={look.tight}>
          <div className={look.split} aria-hidden="true">
            <span style={{ flex: d.ada / total }} />
            <span style={{ flex: d.person / total }} />
            <span style={{ flex: d.default / total }} />
          </div>
          <div className={look.statLine}>
            <span>
              Ada decided <b>{d.ada}</b> · you <b>{d.person}</b>
              {d.default > 0 && (
                <>
                  {' '}
                  · default <b>{d.default}</b>
                </>
              )}
            </span>
          </div>
        </div>
      )}
      {stat.ask_rate !== undefined && (
        <div className={look.tight}>
          <div className={look.bar} aria-hidden="true">
            <span style={{ width: pct(stat.ask_rate ?? 0) }} />
          </div>
          <div className={look.statLine}>
            <span>Asks you</span>
            <b>{pct(stat.ask_rate)}</b>
          </div>
        </div>
      )}
      {agree && agree.asked > 0 && (
        <div className={look.statLine}>
          <span>Right when it asked</span>
          <span>
            <b>{pct(agree.rate)}</b> <span className={look.muted}>({agree.agreed} of {agree.asked})</span>
          </span>
        </div>
      )}
      {!compact && stat.overrules && (
        <div className={look.statLine}>
          <span>Corrected</span>
          <b>{plural(stat.overrules.total, 'time')}</b>
        </div>
      )}
    </>
  );
  return compact ? (
    <Link to={`${botPath(bot.slug)}?tab=gates`} className={look.gate} aria-label={`${name} gate`}>
      {body}
    </Link>
  ) : (
    <div className={look.gate}>{body}</div>
  );
}

/** Where the bot's loop reads and acts: its tool steps, by app and words. */
function toolSteps(bot: Bot) {
  const steps = Array.isArray(bot.spec.loop) ? bot.spec.loop : [];
  const app = (key: string) => bot.connections.find((c) => c.tools.includes(key) || key.startsWith(`${c.app}-`))?.app_name ?? key.split(/[-_]/)[0];
  return steps
    .filter((s) => typeof s.tool === 'string')
    .map((s) => ({ key: String(s.tool), where: `${app(String(s.tool))} · ${toolWords(String(s.tool))}`, asks: Boolean(s.ask) }));
}

/** What the bot watches and when: its schedule, where it reads from, what it does, and where it runs. */
export function Watches({ bot }: { bot: Bot }) {
  const places = useBotPlaces();
  const steps = toolSteps(bot);
  const reads = steps[0];
  const acts = steps.slice(1);
  const place = bot.runs_on ? (places.data?.find((p) => p.id === bot.runs_on)?.name ?? 'your machine') : 'Glyphh cloud';
  const given = bot.schedule?.input;
  return (
    <dl className={look.facts2} aria-label="What it watches">
      <div>
        <dt>When</dt>
        <dd>
          {bot.schedule_summary && bot.schedule?.every !== 'off' ? bot.schedule_summary : 'Only when you run it'}
          {bot.next_run && <small>Next run {bot.next_run}</small>}
        </dd>
      </div>
      <div>
        <dt>Watches</dt>
        <dd>
          {reads ? reads.where : 'What you give it'}
          {given && <small>Each run is given “{given}”</small>}
        </dd>
      </div>
      {acts.length > 0 && (
        <div>
          <dt>Then</dt>
          <dd>
            {acts.map((a) => (
              <span key={a.key} className={look.block}>
                {a.where}
                {a.asks && <span className={look.muted}> · asks you first</span>}
              </span>
            ))}
          </dd>
        </div>
      )}
      <div>
        <dt>Runs on</dt>
        <dd>{place}</dd>
      </div>
    </dl>
  );
}

/** The connector's tools that reach this bot (server docs/specs/bots.md, section 9), each with what it does here. */
export const CLAUDE_TOOLS: ReadonlyArray<{ tool: string; does: string }> = [
  { tool: 'bot_run', does: 'Runs it now, with what Claude gives it' },
  { tool: 'bot_runs', does: 'Reads its runs and what each decided' },
  { tool: 'bot_run_answer', does: 'Answers what it asks you' },
  { tool: 'bot_run_wrong', does: 'Corrects a decision: its gate learns it' },
  { tool: 'bot_gates', does: 'Reads what its gates learned in Ada' },
  { tool: 'bot_approvals', does: 'Everything of yours waiting on you' },
];

/** In the person's Glyphh connection: the tools Claude (claude.ai, Cowork, Claude Code) has for this bot. */
export function InClaude({ bot }: { bot: Bot }) {
  return (
    <>
      <ul className={look.tools} aria-label="Tools in Claude">
        {CLAUDE_TOOLS.map((t) => (
          <li key={t.tool}>
            <code>{t.tool}</code>
            <span>{t.does}</span>
          </li>
        ))}
      </ul>
      <p className={look.note}>
        In your Glyphh connection, with <span className={look.mono}>slug: {bot.slug}</span>.
      </p>
    </>
  );
}
