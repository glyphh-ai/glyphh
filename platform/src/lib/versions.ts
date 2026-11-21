import type { AdaVersion, LearnedSummary, SpecChange } from '@/api/ada';

/**
 * A version's changes in words, from the server's generic diff (`{path, from, to, restates}`): settings by their
 * lever (`k 15 → 20`), roles by their dotted path as the kernel names them (`ticket.about.subject`), anything added or
 * taken away whole by what it is.
 */

const kinds: Record<string, string> = { layers: 'layer', segments: 'segment', roles: 'role', interactions: 'pair' };

/** Where a change is, readably: `settings.k` → `k`; `layers[a].segments[s].roles[color].similarity_weight` → `a.s.color similarity_weight`. */
export function changeLabel(path: string): { kind: string | null; label: string } {
  if (path.startsWith('settings.')) return { kind: null, label: path.slice('settings.'.length) };
  const named = [...path.matchAll(/(\w+)\[([^\]]+)\]/g)];
  if (named.length === 0) return { kind: null, label: path };
  const last = named.at(-1)!;
  const where = named.map((m) => m[2]).join('.');
  const rest = path.slice(last.index + last[0].length).replace(/^\./, '');
  if (rest) return { kind: null, label: `${where} ${rest}` };
  return { kind: kinds[last[1]!] ?? null, label: where };
}

/** A value in a line: on/off, none, a number or text as it is, anything bigger as short JSON. */
export function valueText(value: unknown): string {
  if (value === null || value === undefined) return 'none';
  if (typeof value === 'boolean') return value ? 'on' : 'off';
  if (typeof value === 'number' || typeof value === 'string') return String(value);
  const text = JSON.stringify(value);
  return text.length > 40 ? `${text.slice(0, 39)}…` : text;
}

/** One change in words: `k 15 → 20`, `role a.s.size added`, `pair cs taken away`. */
export function changeText(change: SpecChange): string {
  const { kind, label } = changeLabel(change.path);
  const name = kind ? `${kind} ${label}` : label;
  if (change.from === null || change.from === undefined) return kind ? `${name} added` : `${name} set to ${valueText(change.to)}`;
  if (change.to === null || change.to === undefined) return kind ? `${name} taken away` : `${name} removed`;
  return `${name} ${valueText(change.from)} → ${valueText(change.to)}`;
}

/** What a version changed, in a line, when no one wrote why: `k 15 → 20`, `Re-encoded: seed 5 → 11`. */
export function autoSummary(version: Pick<AdaVersion, 'changes' | 'new_store'>, most = 3): string {
  if (version.changes === null) return 'First version';
  if (version.changes.length === 0) return 'No change to the spec or settings';
  const shown = version.changes.slice(0, most).map(changeText).join('; ');
  const more = version.changes.length - most;
  const text = more > 0 ? `${shown} and ${more} more` : shown;
  return version.new_store ? `Re-encoded: ${text}` : text;
}

/** What one output's store had learned, in a line: `5 roles weighed, 120 words, 2 pairs, tau 0.81`. */
export function learnedText(entry: LearnedSummary[string]): string {
  const parts: string[] = [];
  const roles = Object.keys(entry.roles ?? {}).length;
  const words = Object.values(entry.words ?? {}).reduce((n, w) => n + w, 0);
  const pairs = entry.pairs?.length ?? 0;
  if (entry.roles) parts.push(`${roles} ${roles === 1 ? 'role' : 'roles'} weighed`);
  if (entry.words) parts.push(`${words.toLocaleString('en-GB')} ${words === 1 ? 'word' : 'words'}`);
  if (entry.pairs) parts.push(`${pairs} ${pairs === 1 ? 'pair' : 'pairs'}`);
  if (entry.tau !== undefined) parts.push(`tau ${entry.tau}`);
  return parts.length ? parts.join(', ') : 'Nothing learned';
}
