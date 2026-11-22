import type { BotRun, BotSpec, GateDecision, GateStat, ItemDecision } from '@/api/bots';

/** What a run's own data says Ada decided, read for the chat: who decided, the outcomes there are, the decisions. */

/** 0.18 as `18%`; nothing known as `—`. */
const pct = (rate: number | null | undefined) => (rate === null || rate === undefined ? '—' : `${Math.round(rate * 100)}%`);

/** Who decided: Ada from what she has seen (with how sure she was), the person, or the default. */
export function byWords(d: { by: string; p?: number | null }) {
  if (d.by === 'ada') return d.p ? `Ada · ${pct(d.p)} sure` : 'Ada';
  if (d.by === 'person') return 'You';
  if (d.by === 'default') return 'Default';
  if (d.by === 'deferred') return 'Next run';
  return d.by;
}

/** The outcomes of one thing a bot decides, as its definition names them (`outcomes`, or `options` in older ones). */
export function outcomesOf(spec: BotSpec, gate: string, stat?: GateStat): string[] {
  if (stat?.outcomes?.length) return stat.outcomes;
  const g = (spec.gates ?? {})[gate] as { outcomes?: unknown; options?: unknown } | undefined;
  const list = g?.outcomes ?? g?.options;
  return Array.isArray(list) ? list.map(String) : [];
}

export type RunDecision = GateDecision & { gate: string; items: ItemDecision[] };

/**
 * The decisions one run made (`run.data._gates`), each with its items when it decided over many
 * (`run.data[step].decisions`, the step it sits on).
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
