import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

/**
 * Recents (the server's /v1/recents): every past run a person can go back to, one bot's or the crew's, newest first.
 * A run that waits on the person is `waiting`; `needs_you` counts those across the org, whatever the filters (the top
 * bar's chip). Pinned and archived are each person's own; delete removes the run for everyone.
 */
export type Recent = {
  /** The run's own id: a bot run's, or a crew run's. */
  id: string;
  kind: 'bot' | 'crew';
  /** The task's first line; empty when the run had no task. */
  title: string;
  /** The bot whose run it is; none for the crew's. */
  bot_slug: string | null;
  /** The bot's name; "Crew" for the crew's. */
  bot_name: string;
  /** A crew run's workspace on the server (its runs are read through it); none for a bot's. */
  project_slug: string | null;
  /** The repo a crew run worked in, `owner/name`, and its branch; none for a bot's chat. */
  workspace: string | null;
  branch: string | null;
  runs_on: string | null;
  status: string;
  waiting: boolean;
  pinned: boolean;
  archived: boolean;
  created_at: string;
};
export type Recents = { recents: Recent[]; next_cursor: string | null; needs_you: number; archived_count: number };
export type RecentsQuery = { q?: string; waiting?: boolean; archived?: boolean; limit?: number; cursor?: string };

export const recentKeys = {
  all: ['recents'] as const,
  list: (query: RecentsQuery) => ['recents', query.q ?? '', Boolean(query.waiting), Boolean(query.archived), query.limit ?? 0] as const,
};

const search = (query: RecentsQuery) => {
  const p = new URLSearchParams();
  if (query.q) p.set('q', query.q);
  if (query.waiting) p.set('waiting', '1');
  if (query.archived) p.set('archived', '1');
  if (query.limit) p.set('limit', String(query.limit));
  if (query.cursor) p.set('cursor', query.cursor);
  const s = p.toString();
  return s ? `?${s}` : '';
};

/** How many rows a page of the dropdown holds; the next is asked for by the cursor the one before gave. */
export const RECENTS_PAGE = 30;

/** The dropdown's list, a page at a time: each page after the first by the cursor of the one before. */
export const useRecentsPaged = (query: Omit<RecentsQuery, 'cursor' | 'limit'> = {}, every = 15_000) =>
  useInfiniteQuery({
    queryKey: [...recentKeys.list(query), 'paged'] as const,
    initialPageParam: '',
    queryFn: ({ pageParam }) => api.get<Recents>(`/recents${search({ ...query, limit: RECENTS_PAGE, cursor: pageParam || undefined })}`),
    getNextPageParam: (last) => last.next_cursor || undefined,
    refetchInterval: every,
  });

/** A read of the list, asked for again every 15 seconds so a run that starts to wait shows without a reload. */
export const useRecents = (query: RecentsQuery = {}, { enabled = true, every = 15_000 }: { enabled?: boolean; every?: number } = {}) =>
  useQuery({ queryKey: recentKeys.list(query), queryFn: () => api.get<Recents>(`/recents${search(query)}`), refetchInterval: every, enabled });

/** The runs that wait on a person now: the chip's count, and which bots carry "Needs you" in the rail. */
export const useWaiting = () => useRecents({ waiting: true, limit: 100 });

const one = (id: string) => `/recents/${encodeURIComponent(id)}`;

function useWrite<A>(fn: (args: A) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: recentKeys.all }) });
}

export const usePinRecent = () => useWrite(({ id, pinned }: { id: string; pinned: boolean }) => api.post<Recent>(`${one(id)}/${pinned ? 'pin' : 'unpin'}`));
export const useArchiveRecent = () => useWrite(({ id, archived }: { id: string; archived: boolean }) => api.post<Recent>(`${one(id)}/${archived ? 'archive' : 'unarchive'}`));
/** Deletes the run for the whole org; refused (409 `run_live`) while it is going or waiting. */
export const useDeleteRecent = () => useWrite((id: string) => api.delete<void>(one(id)));
