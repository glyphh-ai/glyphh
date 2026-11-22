import { useQuery } from '@tanstack/react-query';
import { api } from './client';

/**
 * The one place the browser asks a rrotor itself, at the machine's own address and not through Glyphh: the folders
 * that machine's owner offers, for choosing which a bot may use. The browser first asks Glyphh for a short ticket for
 * that one machine (`POST /bots/places/{id}/ticket`), then reads `GET <rrotor>/v1/folders?under=<path>` with it; with
 * no `under` the machine answers the folders its owner shares (none until they share one). Nothing of the listing goes
 * to or through Glyphh.
 */
export type MachineFolder = { path: string; name: string };
type Ticket = { token: string; expires_in: number; url: string };

const tickets = new Map<string, { ticket: Ticket; until: number }>();

async function ticketFor(place: string, fresh = false): Promise<Ticket> {
  const kept = tickets.get(place);
  if (!fresh && kept && kept.until > Date.now()) return kept.ticket;
  const ticket = await api.post<Ticket>(`/bots/places/${encodeURIComponent(place)}/ticket`);
  tickets.set(place, { ticket, until: Date.now() + Math.max(0, ticket.expires_in - 30) * 1000 });
  return ticket;
}

export async function foldersUnder(place: string, under: string): Promise<MachineFolder[]> {
  const ask = async (fresh: boolean) => {
    const ticket = await ticketFor(place, fresh);
    const url = `${ticket.url.replace(/\/+$/, '')}/v1/folders${under ? `?under=${encodeURIComponent(under)}` : ''}`;
    try {
      return await fetch(url, { credentials: 'omit', headers: { accept: 'application/json', authorization: `Bearer ${ticket.token}` } });
    } catch {
      throw new Error('That machine did not answer. Check it is on and linked to Glyphh.');
    }
  };
  let response = await ask(false);
  if (response.status === 401) response = await ask(true);
  if (!response.ok) {
    const said = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    throw new Error(said?.error?.message || 'That machine could not list its folders.');
  }
  const body = (await response.json()) as { folders?: MachineFolder[] };
  return Array.isArray(body.folders) ? body.folders : [];
}

/** The folders under `under` on the org's rrotor `place`; asked only while there is a machine to ask. */
export const useMachineFolders = (place: string | null | undefined, under: string) =>
  useQuery({
    queryKey: ['rrotor-folders', place ?? '', under],
    queryFn: () => foldersUnder(place!, under),
    enabled: Boolean(place),
    retry: false,
    staleTime: 30_000,
  });
