import { api } from './client';

/**
 * What the work panels read of a rrotor, straight from the browser at the machine's own address: the repositories the
 * crew worked in there, their files, a branch's changes and the live record of the commands a turn ran. The browser
 * asks Glyphh only for a short ticket for that one machine (`POST /bots/places/{id}/ticket`, as the folder picker does:
 * src/api/rrotorFolders.ts) and then reads `<rrotor>/v1/work...` with it. Nothing a panel shows goes to or through
 * Glyphh, which keeps none of it.
 */
export type Workspace = { id: string; name: string; kind: string; branch: string | null; branches: string[] };
export type Entry = { name: string; path: string; kind: 'dir' | 'file'; size: number | null };
export type Tree = { under: string; entries: Entry[]; truncated?: boolean };
export type WorkFile = { path: string; size: number; binary: boolean; text: string | null; truncated: boolean };
export type Changed = {
  path: string;
  status: 'added' | 'modified' | 'deleted';
  added: number;
  removed: number;
  binary: boolean;
  before: string | null;
  after: string | null;
};
export type Diff = { base: string; branch: string | null; files: Changed[]; truncated: boolean };
export type TermLine = { n: number; at: string; kind: 'cmd' | 'out' | 'err' | 'note'; text: string };
export type Term = { lines: TermLine[]; next: number; live: boolean };

/** A machine's refusal, in its own words where it has them. `code` is the rrotor's (E_BUSY, E_TOO_BIG, …). */
export class WorkError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'WorkError';
    this.status = status;
    this.code = code;
  }
}

export const NO_ANSWER = 'That machine did not answer. Check it is on and linked to Glyphh; a rrotor on a computer answers only in a browser on that same computer.';
const SAID: Record<string, string> = {
  E_BUSY: 'A bot is working in this repository right now. Save again when its turn ends.',
  E_HEAD_ONLY: 'This machine is a standby of its cluster and keeps no working files. Ask the cluster’s head.',
  E_TOO_BIG: 'That file is too big to show here.',
};

type Ticket = { token: string; expires_in: number; url: string };
const tickets = new Map<string, { ticket: Ticket; until: number }>();

async function ticketFor(place: string, fresh = false): Promise<Ticket> {
  const kept = tickets.get(place);
  if (!fresh && kept && kept.until > Date.now()) return kept.ticket;
  const ticket = await api.post<Ticket>(`/bots/places/${encodeURIComponent(place)}/ticket`);
  tickets.set(place, { ticket, until: Date.now() + Math.max(0, ticket.expires_in - 30) * 1000 });
  return ticket;
}

/** Forgets the tickets held (the tests', between cases). */
export const forgetTickets = () => tickets.clear();

const query = (given: Record<string, string | number | undefined>) => {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(given)) if (v !== undefined && v !== '') q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : '';
};

/** One request of the machine with its ticket; a 401 fetches a fresh ticket and asks once more. */
async function ask(place: string, path: string, init: { method?: string; body?: unknown } = {}): Promise<Response> {
  const once = async (fresh: boolean) => {
    const ticket = await ticketFor(place, fresh);
    const headers: Record<string, string> = { authorization: `Bearer ${ticket.token}` };
    if (init.body !== undefined) headers['content-type'] = 'application/json';
    try {
      return await fetch(`${ticket.url.replace(/\/+$/, '')}/v1/work${path}`, {
        method: init.method ?? 'GET',
        credentials: 'omit',
        headers,
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
      });
    } catch {
      throw new WorkError(0, 'E_NO_ANSWER', NO_ANSWER);
    }
  };
  let response = await once(false);
  if (response.status === 401) response = await once(true);
  if (!response.ok) {
    const said = (await response.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
    const code = said?.error?.code ?? 'E_HTTP';
    throw new WorkError(response.status, code, SAID[code] ?? said?.error?.message ?? 'That machine could not answer that.');
  }
  return response;
}

const read = async <T>(place: string, path: string, init?: { method?: string; body?: unknown }): Promise<T> => (await ask(place, path, init)).json() as Promise<T>;
const ws = (id: string) => `/${encodeURIComponent(id)}`;

/** The machine `place` (one of the org's rrotors), as the work panels ask it. */
export const workClient = (place: string) => ({
  place,
  workspaces: async () => (await read<{ workspaces?: Workspace[] }>(place, '')).workspaces ?? [],
  tree: (id: string, under = '') => read<Tree>(place, `${ws(id)}/tree${query({ under })}`),
  file: (id: string, path: string, ref?: string) => read<WorkFile>(place, `${ws(id)}/file${query({ path, ref })}`),
  /** A file's own bytes (an image to show), at most 10 MB. */
  raw: async (id: string, path: string, ref?: string) => (await ask(place, `${ws(id)}/file${query({ path, ref, raw: 1 })}`)).blob(),
  /** Writes the working copy only: a save no turn commits is dropped when the next turn starts. */
  save: (id: string, path: string, text: string) => read<{ path: string; size: number }>(place, `${ws(id)}/file${query({ path })}`, { method: 'PUT', body: { text } }),
  diff: (id: string, branch?: string, base?: string) => read<Diff>(place, `${ws(id)}/diff${query({ branch, base })}`),
  /** The command record from line `after` on (the last answer's `next`). */
  terminal: (id: string, after = 0) => read<Term>(place, `${ws(id)}/terminal${query({ after })}`),
});
export type WorkClient = ReturnType<typeof workClient>;
