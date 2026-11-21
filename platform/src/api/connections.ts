import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useCallback, useSyncExternalStore } from 'react';
import { api } from './client';
import { botKeys, type Connection, type ConnectionTool, type ConnectorApp } from './bots';

/**
 * The connections catalog: every app Pipedream connects (`GET /v1/connections/apps`, a page at a time by its cursor),
 * the org's own connections beside it, and one app's tools.
 */
export type AppPage = { apps: ConnectorApp[]; next_cursor: string | null };

export const catalogKey = (q: string) => [...botKeys.connections, '~catalog', q] as const;

/** The catalog, searched by name; each page after the first asked for by the cursor the one before gave. */
export const useAppCatalog = (q: string, enabled = true) =>
  useInfiniteQuery({
    queryKey: catalogKey(q),
    enabled,
    initialPageParam: '',
    queryFn: ({ pageParam }) =>
      api.get<AppPage>(`/connections/apps?q=${encodeURIComponent(q)}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`),
    getNextPageParam: (last) => last.next_cursor || undefined,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });

/** One app of the catalog, found by its slug (a search for it, the exact slug taken). */
export const useCatalogApp = (slug: string, enabled = true) =>
  useQuery({
    queryKey: [...botKeys.connections, '~app', slug],
    enabled,
    queryFn: async () => (await api.get<AppPage>(`/connections/apps?q=${encodeURIComponent(slug)}`)).apps.find((a) => a.slug === slug) ?? null,
    staleTime: 5 * 60_000,
  });

/** An app's tools, read through one of the org's connections to it. */
export const useAppTools = (connectionId: string | undefined) =>
  useQuery({
    queryKey: botKeys.tools(connectionId ?? ''),
    enabled: connectionId !== undefined,
    queryFn: async () => (await api.get<{ tools: ConnectionTool[] }>(`/connections/${encodeURIComponent(connectionId!)}/tools`)).tools,
    staleTime: 5 * 60_000,
  });

/** The org's connections, one entry per app (an app signed in to with two accounts is one app with two). */
export type ConnectedApp = { app: string; name: string; icon: string | null; accounts: Connection[] };

export function byApp(connections: Connection[]): ConnectedApp[] {
  const apps = new Map<string, ConnectedApp>();
  for (const c of connections) {
    const found = apps.get(c.app) ?? { app: c.app, name: c.app_name, icon: c.app_icon, accounts: [] };
    found.accounts.push(c);
    apps.set(c.app, found);
  }
  return [...apps.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Read-only when its key or name says it only reads; anything else writes, sends or deletes. */
const READS = /(^|[-_ ])(get|list|find|search|read|lookup|retrieve|fetch|query|download|export)([-_ ]|$)/i;
export const readsOnly = (tool: ConnectionTool) => READS.test(tool.key) || READS.test(tool.name);

/**
 * Which of a connection's tools the org's bots may be given: allowed or blocked, per tool. The server keeps no such
 * choice per connection yet (a bot's own scope is what it may use), so this one is kept in this browser.
 */
export type ToolChoice = 'allow' | 'block';
type Choices = Record<string, ToolChoice>;
const storeKey = (connectionId: string) => `glyphh.connection-tools.${connectionId}`;
const listeners = new Set<() => void>();

function read(connectionId: string): string {
  try {
    return localStorage.getItem(storeKey(connectionId)) ?? '{}';
  } catch {
    return '{}';
  }
}

export function useToolChoices(connectionId: string) {
  const raw = useSyncExternalStore(
    (changed) => {
      listeners.add(changed);
      return () => listeners.delete(changed);
    },
    () => read(connectionId),
  );
  const choices = JSON.parse(raw) as Choices;
  const set = useCallback(
    (keys: string[], choice: ToolChoice) => {
      const next = { ...(JSON.parse(read(connectionId)) as Choices) };
      for (const key of keys) next[key] = choice;
      try {
        localStorage.setItem(storeKey(connectionId), JSON.stringify(next));
      } catch {
        /* storage off: the choice holds until the page is left */
      }
      listeners.forEach((l) => l());
    },
    [connectionId],
  );
  return { choiceOf: (key: string): ToolChoice => choices[key] ?? 'allow', set };
}
