import { http, HttpResponse } from 'msw';
import type { Decision, DecisionDetail, GateStats, Precedent } from '@/api/botDecisions';
import { apiError } from './server';

/**
 * A bot's decisions as the server answers them (/v1/bots/{slug}/decisions, /v1/bot-decisions/{id}): searched,
 * filtered, sorted and paged by cursor, and trained (relabel, confirm, a precedent forgotten), held in state so each
 * write shows on the next read.
 */
const v1 = (path: string) => `*/api/v1${path}`;

export const decision = (given: Partial<Decision> = {}): Decision => ({
  id: 'd-1',
  run_id: 'r-done',
  gate: 'easy',
  step: 'decide',
  key: 'm1',
  kind: 'each',
  label: 'Lunch on Friday?',
  fields: { subject: 'Lunch on Friday?', from: 'ada@example.com' },
  outcome: 'answer',
  now: 'answer',
  who: 'ada',
  mode: '',
  confidence: 0.97,
  guess: null,
  recorded: true,
  corrected: null,
  confirmed: false,
  outcomes: ['answer', 'leave'],
  at: '2026-11-20T09:01:00Z',
  ...given,
});

export const precedent = (given: Partial<Precedent> = {}): Precedent => ({
  id: 'p-1',
  outcome: 'answer',
  similarity: 0.91,
  label: 'Coffee next week?',
  decision_id: null,
  ...given,
});

type Options = { decisions?: Decision[]; precedents?: Precedent[]; stats?: GateStats[] };

const SORTS = {
  time: (d: Decision) => d.at,
  confidence: (d: Decision) => d.confidence ?? -1,
  gate: (d: Decision) => d.gate,
  outcome: (d: Decision) => d.now ?? '',
} as const;

export function decisionsFake({ decisions = [], precedents = [], stats = [] }: Options = {}) {
  const state = { decisions: structuredClone(decisions), precedents: structuredClone(precedents), seen: [] as string[], bodies: [] as unknown[] };
  const find = (id: unknown) => state.decisions.find((d) => d.id === id);
  const gates = () => Object.fromEntries(state.decisions.map((d) => [d.gate, d.outcomes]));
  const trained = (rows: Decision[], said: string) => HttpResponse.json({ decisions: rows, precedents: state.precedents.length + rows.length, said });
  const relabel = (rows: Decision[], outcome: string) => {
    for (const d of rows) Object.assign(d, { corrected: outcome, now: outcome, recorded: true });
    return trained(rows, `Gate ${rows[0]!.gate} learned ${rows.length} as ${outcome}`);
  };
  const confirm = (rows: Decision[]) => {
    for (const d of rows) Object.assign(d, { confirmed: true, recorded: true });
    return trained(rows, `Gate ${rows[0]!.gate} kept ${rows.length} as right`);
  };

  const handlers = [
    http.get(v1('/bots/:slug/decisions'), ({ request }) => {
      const p = new URL(request.url).searchParams;
      const words = (p.get('q') ?? '').toLowerCase().split(/\s+/).filter(Boolean);
      const sort = (p.get('sort') ?? 'time') as keyof typeof SORTS;
      const asc = p.get('order') === 'asc';
      const rows = state.decisions
        .filter((d) => words.every((w) => `${d.label} ${Object.values(d.fields).join(' ')}`.toLowerCase().includes(w)))
        .filter((d) => !p.get('gate') || d.gate === p.get('gate'))
        .filter((d) => !p.get('outcome') || d.now === p.get('outcome'))
        .filter((d) => !p.get('who') || d.who === p.get('who'))
        .filter((d) => !p.get('run_id') || d.run_id === p.get('run_id'))
        .filter((d) => !p.has('corrected') || (d.corrected !== null) === (p.get('corrected') === 'true'))
        .sort((a, b) => {
          const [x, y] = [SORTS[sort](a), SORTS[sort](b)];
          return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1);
        });
      const limit = Number(p.get('limit') ?? 25);
      const start = Number(p.get('cursor') ?? 0);
      const page = rows.slice(start, start + limit);
      state.seen.push(`decisions ${p.toString()}`);
      return HttpResponse.json({ decisions: page, total: rows.length, next_cursor: start + limit < rows.length ? String(start + limit) : null, gates: gates() });
    }),
    http.get(v1('/bots/:slug/decisions/stats'), () => HttpResponse.json({ gates: stats })),
    http.get(v1('/bot-decisions/:id'), ({ params }) => {
      const d = find(params.id);
      if (!d) return apiError(404, 'E_NOT_FOUND', 'There is no such decision.');
      const detail: DecisionDetail = { ...d, case: { m: { s: d.fields } }, precedents: state.precedents };
      return HttpResponse.json(detail);
    }),
    http.post(v1('/bot-decisions/:id/relabel'), async ({ params, request }) => {
      const d = find(params.id);
      if (!d) return apiError(404, 'E_NOT_FOUND', 'There is no such decision.');
      const body = (await request.json()) as { outcome: string };
      state.bodies.push(body);
      state.seen.push(`relabel ${d.id}`);
      return relabel([d], body.outcome);
    }),
    http.post(v1('/bot-decisions/:id/confirm'), ({ params }) => {
      const d = find(params.id);
      if (!d) return apiError(404, 'E_NOT_FOUND', 'There is no such decision.');
      state.seen.push(`confirm ${d.id}`);
      return confirm([d]);
    }),
    http.post(v1('/bots/:slug/decisions/relabel'), async ({ request }) => {
      const body = (await request.json()) as { ids: string[]; outcome: string };
      state.bodies.push(body);
      state.seen.push(`relabel ${body.ids.join(',')}`);
      return relabel(state.decisions.filter((d) => body.ids.includes(d.id)), body.outcome);
    }),
    http.post(v1('/bots/:slug/decisions/confirm'), async ({ request }) => {
      const body = (await request.json()) as { ids: string[] };
      state.seen.push(`confirm ${body.ids.join(',')}`);
      return confirm(state.decisions.filter((d) => body.ids.includes(d.id)));
    }),
    http.delete(v1('/bots/:slug/gates/:gate/precedents/:id'), ({ params }) => {
      state.precedents = state.precedents.filter((p) => p.id !== params.id);
      state.seen.push(`forget ${String(params.id)}`);
      return HttpResponse.json({ gate: params.gate, id: params.id, precedents: state.precedents.length });
    }),
  ];
  return { state, handlers };
}
