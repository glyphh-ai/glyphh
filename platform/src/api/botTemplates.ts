import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Look } from '@/bots/cat/look';
import { api } from './client';

/**
 * The Marketplace's bots (the server's /v1/bot-templates): bots Glyphh builds to do one job, each copied into the org
 * as a bot of its own when added. A template names the connections it needs, the tools it uses and its gates.
 */
export type RequiredApp = { slug: string; name: string; icon: string | null };
export type BotTemplate = {
  slug: string;
  name: string;
  summary: string;
  description: string;
  look: Look;
  model: string;
  spec: Record<string, unknown>;
  skills: Record<string, string>;
  required_apps: RequiredApp[];
  tools: string[];
  gates: string[];
};
export type AddedBot = { slug: string; name: string };

export const botTemplateKeys = { all: ['bot-templates'] as const };

export const useBotTemplates = () =>
  useQuery({
    queryKey: botTemplateKeys.all,
    queryFn: async () => (await api.get<{ templates: BotTemplate[] }>('/bot-templates')).templates,
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
