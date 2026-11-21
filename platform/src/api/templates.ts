import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

/**
 * The template library (`docs/specs/templates.md` in the server): bundles a person installs for themselves, each
 * making Ada models of their own and adding tools to their own connector. Through /api/v1 with the platform's sign-in.
 */
export type TemplateModel = { key: string; title: string; about: string; model: string };
export type TemplateTool = { name: string; title: string; description: string };
export type Template = {
  slug: string;
  name: string;
  category: string;
  summary: string;
  version: number;
  models: TemplateModel[];
  tools: TemplateTool[];
  instructions: string;
  installed: boolean;
  installed_version: number | null;
};

export const templateKeys = { all: ['templates'] as const };

export const useTemplates = () =>
  useQuery({ queryKey: templateKeys.all, queryFn: async () => (await api.get<{ templates: Template[] }>('/templates')).templates });

/** One template, for its details page (`GET /v1/templates/{slug}`); under the list's key, so an install refreshes it. */
export const useTemplate = (slug: string) =>
  useQuery({ queryKey: [...templateKeys.all, slug], queryFn: () => api.get<Template>(`/templates/${encodeURIComponent(slug)}`) });

function useTemplateWrite(fn: (slug: string) => Promise<Template>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: templateKeys.all }) });
}

export const useInstallTemplate = () => useTemplateWrite((slug) => api.post<Template>(`/templates/${encodeURIComponent(slug)}/install`));
export const useRemoveTemplate = () => useTemplateWrite((slug) => api.delete<Template>(`/templates/${encodeURIComponent(slug)}/install`));
