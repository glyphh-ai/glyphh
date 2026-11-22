import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { readResponse } from '@/api/client';

/**
 * The games' admin, through the platform's own route handlers (/api/games): the platform calls each game's admin
 * tools server-side with that game's key. The browser never sees a key.
 */

export type Revenue = { today: number | null; d7: number | null; d30: number | null; all: number | null };

export type Summary = {
  players: number | null;
  playersAre: string;
  new24: number | null;
  active24: number | null;
  labels: [string, string];
  revenue: Revenue | null;
  pending: Array<{ label: string; count: number; tab: string }>;
};

export type GameRow = {
  id: string;
  name: string;
  site: string;
  icon: string;
  connected: boolean;
  health: { ok: boolean; build: string | null; ms: number };
  summary: Summary | null;
  error: string | null;
};

export type Overview = { games: GameRow[]; at: number };

export type Args = Record<string, unknown>;

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { accept: 'application/json', 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  return readResponse<T>(response);
}

/** One admin tool of one game; its answer as the game gave it. */
export async function runTool(game: string, tool: string, args: Args = {}): Promise<unknown> {
  const { result } = await post<{ result: unknown }>(`/api/games/${game}/tools/${tool}`, { arguments: args });
  return result;
}

export const useGamesOverview = () =>
  useQuery({
    queryKey: ['games', 'overview'],
    queryFn: async () => readResponse<Overview>(await fetch('/api/games/overview', { credentials: 'same-origin' })),
    refetchInterval: 60_000,
  });

/** A tool that only reads, asked again whenever its arguments change. */
export const useGameRead = (game: string, tool: string, args: Args, enabled = true) =>
  useQuery({
    queryKey: ['games', game, tool, args],
    queryFn: () => runTool(game, tool, args),
    enabled,
    placeholderData: keepPreviousData,
  });

/**
 * An action; afterwards everything shown of that game, and the overview, is read again. A `preview` (the game saying
 * what would happen, changing nothing) is not followed by a read.
 */
export function useGameAction(game: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ tool, args }: { tool: string; args: Args; preview?: boolean }) => runTool(game, tool, args),
    onSuccess: (_result, { preview }) => {
      if (preview) return;
      void client.invalidateQueries({ queryKey: ['games', game] });
      void client.invalidateQueries({ queryKey: ['games', 'overview'] });
    },
  });
}
