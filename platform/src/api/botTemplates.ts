import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Look } from '@/bots/cat/look';
import type { RunsWhere } from './bots';
import { api, ApiError } from './client';

/**
 * The Marketplace's bots (the server's /v1/bot-templates): bots Glyphh builds to do one job, each copied into the org
 * as a bot of its own when added. A template says what it does, the apps it needs connected, what it decides, things
 * to ask it, and where it can run. How it works inside is not part of what the server sends.
 */
export type TemplateApp = { app: string; name: string; tools: string[] };
/** One thing the bot decides: its name, the question it settles and the outcomes there are. */
export type TemplateDecision = { name: string; question: string; outcomes: string[] };
export type BotTemplate = {
  slug: string;
  version: string;
  name: string;
  /** Its tagline: what it is for, in a line. */
  summary: string;
  description: string;
  look: Look;
  apps: TemplateApp[];
  decides: TemplateDecision[];
  /** Things to ask it. */
  examples: string[];
  /** Its standing task: what it does when it runs on its own. */
  task: string;
  schedule: unknown;
  /** Where it can run: Glyphh cloud, a rrotor, or both. */
  runs_on: RunsWhere[];
};
export type AddedBot = { slug: string; name: string };

/** A template as the server sends it: any list may be missing, and an app may come without its name. */
export type ServedTemplate = Partial<Omit<BotTemplate, 'apps'>> & Pick<BotTemplate, 'slug' | 'name'> & { apps?: Array<Partial<TemplateApp> & { app: string }> };

const named = (slug: string): string =>
  slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

export const fromServer = (t: ServedTemplate): BotTemplate => ({
  slug: t.slug,
  version: t.version ?? '',
  name: t.name,
  summary: t.summary ?? '',
  description: t.description ?? '',
  look: (t.look ?? {}) as Look,
  apps: (t.apps ?? []).map((a) => ({ app: a.app, name: a.name || named(a.app), tools: a.tools ?? [] })),
  decides: (t.decides ?? []).map((d) => ({ name: d.name, question: d.question ?? '', outcomes: d.outcomes ?? [] })),
  examples: t.examples ?? [],
  task: t.task ?? '',
  schedule: t.schedule ?? null,
  runs_on: t.runs_on?.length ? t.runs_on : ['cloud', 'rrotor'],
});

/** A decision's name as words: `needs_reply` is "needs reply". */
export const decisionName = (name: string): string => name.replace(/[_-]+/g, ' ').trim();
/** What it decides, one line each: "urgency (urgent, normal, spam)". */
export const decidesLines = (decides: TemplateDecision[]): string[] =>
  decides.map((d) => (d.outcomes.length ? `${decisionName(d.name)} (${d.outcomes.join(', ')})` : decisionName(d.name)));

/** The pills for where it can run, in a fixed order: "Cloud" when Glyphh cloud can run it, "rrotor" when a rrotor can. */
export const runsOnPills = (runsOn: RunsWhere[]): string[] => [...(runsOn.includes('cloud') ? ['Cloud'] : []), ...(runsOn.includes('rrotor') ? ['rrotor'] : [])];

/**
 * A template that needs a rrotor, added by an org with none linked (422, reason `rrotor`): the server's plain
 * sentence and where one is set up. Nothing for any other refusal.
 */
export function needsRrotor(error: unknown): { message: string; setupUrl: string } | null {
  if (!(error instanceof ApiError) || error.status !== 422 || error.detail.reason !== 'rrotor') return null;
  const said = error.detail.message;
  const url = error.detail.setup_url;
  return { message: typeof said === 'string' && said ? said : error.message, setupUrl: typeof url === 'string' ? url : '' };
}

export const botTemplateKeys = { all: ['bot-templates'] as const };

export const useBotTemplates = () =>
  useQuery({
    queryKey: botTemplateKeys.all,
    queryFn: async () => (await api.get<{ templates: ServedTemplate[] }>('/bot-templates')).templates.map(fromServer),
  });

/** One bot template, from the list (the list is small and read once). */
export const useBotTemplate = (slug: string) => {
  const all = useBotTemplates();
  return { ...all, data: all.data?.find((t) => t.slug === slug), missing: all.data !== undefined && !all.data.some((t) => t.slug === slug) };
};

/** A template copied into the org as a bot of its own. */
export function useAddBotTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.post<AddedBot>(`/bot-templates/${encodeURIComponent(slug)}/install`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['bots'] }),
  });
}
