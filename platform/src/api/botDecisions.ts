import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

/**
 * A bot's decisions (the server's /v1/bots/{slug}/decisions and /v1/bot-decisions): one row per item per gate per
 * run, each readable (a label and fields drawn from the item, never raw JSON), searched, filtered, sorted and paged
 * by cursor; and the gate trained from them, each through its Ada model (relabel, confirm, a case by hand, a
 * precedent forgotten), its stats and a backtest of the gates as they are now.
 */
export type Who = 'ada' | 'you' | 'default';
export type DecisionSort = 'time' | 'confidence' | 'gate' | 'outcome';
export type Decision = {
  id: string;
  run_id: string | null;
  gate: string;
  step: string;
  key: string;
  /** gate (one case a run), each (one item of many), code, or case (added by hand). */
  kind: string;
  label: string;
  fields: Record<string, string>;
  outcome: string | null;
  /** What it is now: its correction, else what the gate said. */
  now: string | null;
  who: Who;
  mode: string;
  confidence: number | null;
  guess: string | null;
  recorded: boolean;
  corrected: string | null;
  confirmed: boolean;
  outcomes: string[];
  at: string;
};
export type DecisionPage = { decisions: Decision[]; total: number; next_cursor: string | null; gates: Record<string, string[]> };
export type Precedent = { id: string; outcome: unknown; similarity: number | null; label: string | null; decision_id: string | null };
export type DecisionDetail = Decision & { case: unknown; precedents: Precedent[] };
export type Trained = { decisions: Decision[]; precedents: number; said: string };
export type GateDay = { day: string; decisions: number; ask_rate: number | null; agreement: number | null; accuracy: number | null };
export type GateStats = {
  gate: string;
  decisions: number;
  by: Record<Who, number>;
  corrected: number;
  confirmed: number;
  ask_rate: number | null;
  agreement: number | null;
  accuracy: number | null;
  days: GateDay[];
};
/** What the listing is asked: its search words, filters, sort and page. */
export type DecisionQuery = {
  q?: string;
  gate?: string;
  outcome?: string;
  who?: Who;
  corrected?: boolean;
  since?: string;
  until?: string;
  run_id?: string;
  sort?: DecisionSort;
  order?: 'asc' | 'desc';
  cursor?: string;
  limit?: number;
};

export const decisionKeys = {
  all: (slug: string) => ['bots', slug, 'decisions'] as const,
  page: (slug: string, query: DecisionQuery) => ['bots', slug, 'decisions', query] as const,
  one: (id: string) => ['bot-decisions', id] as const,
  stats: (slug: string, gate?: string) => ['bots', slug, 'decision-stats', gate ?? ''] as const,
};

const bot = (slug: string) => `/bots/${encodeURIComponent(slug)}`;
const decision = (id: string) => `/bot-decisions/${encodeURIComponent(id)}`;

/** The query as URL parameters, leaving out what is not set. */
export function queryString(query: DecisionQuery): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== '') params.set(k, String(v));
  const text = params.toString();
  return text ? `?${text}` : '';
}

export const useDecisions = (slug: string, query: DecisionQuery, every?: number) =>
  useQuery({
    queryKey: decisionKeys.page(slug, query),
    queryFn: () => api.get<DecisionPage>(`${bot(slug)}/decisions${queryString(query)}`),
    placeholderData: keepPreviousData,
    refetchInterval: every,
  });
export const useDecision = (id: string | null) =>
  useQuery({ queryKey: decisionKeys.one(id ?? ''), queryFn: () => api.get<DecisionDetail>(decision(id!)), enabled: id !== null });
export const useDecisionStats = (slug: string, gate?: string) =>
  useQuery({
    queryKey: decisionKeys.stats(slug, gate),
    queryFn: async () => (await api.get<{ gates: GateStats[] }>(`${bot(slug)}/decisions/stats${queryString({ gate })}`)).gates,
  });

/** A write that trains the bot's gates: its decisions, one decision and its gates' stats read again after. */
function useTraining<A, R>(slug: string, write: (args: A) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: write,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: decisionKeys.all(slug) }),
        client.invalidateQueries({ queryKey: ['bot-decisions'] }),
        client.invalidateQueries({ queryKey: ['bots', slug, 'decision-stats'] }),
        client.invalidateQueries({ queryKey: ['bots', slug, 'gates'] }),
      ]);
    },
  });
}

export const useRelabel = (slug: string) =>
  useTraining(slug, ({ ids, outcome }: { ids: string[]; outcome: string }) =>
    ids.length === 1
      ? api.post<Trained>(`${decision(ids[0]!)}/relabel`, { outcome })
      : api.post<Trained>(`${bot(slug)}/decisions/relabel`, { ids, outcome }),
  );
export const useConfirm = (slug: string) =>
  useTraining(slug, (ids: string[]) =>
    ids.length === 1 ? api.post<Trained>(`${decision(ids[0]!)}/confirm`) : api.post<Trained>(`${bot(slug)}/decisions/confirm`, { ids }),
  );
export const useForgetPrecedent = (slug: string) =>
  useTraining(slug, ({ gate, id }: { gate: string; id: string }) =>
    api.delete<{ gate: string; id: string; precedents: number }>(
      `${bot(slug)}/gates/${encodeURIComponent(gate)}/precedents/${encodeURIComponent(id)}`,
    ),
  );
