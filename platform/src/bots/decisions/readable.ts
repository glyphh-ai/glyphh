/**
 * A run's data made readable: an item's title drawn from its fields (never raw JSON), a tool's answer told apart from
 * an agent's text, and the steps a run's loop ran in order. The same rules the server's decisions follow.
 */
const TITLES = ['title', 'subject', 'summary', 'name', 'headline', 'label', 'snippet', 'text', 'body'];
const SKIPPED = new Set(['id', 'node_id', 'url', 'key']);
/** Keys of a run's data that are the runner's own bookkeeping, not a step's answer. */
export const BOOKKEEPING = new Set(['_gates', '_each', '_asked']);

export type Obj = Record<string, unknown>;
export const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);
const plain = (v: unknown): v is string | number | boolean => ['string', 'number', 'boolean'].includes(typeof v);
const short = (text: string, n = 140) => {
  const line = text.replace(/\s+/g, ' ').trim();
  return line.length <= n ? line : `${line.slice(0, n - 1)}…`;
};

/** An item's title: its first title-like field, else its first few plain fields, else a word for what it is. */
export function itemLabel(item: unknown): string {
  if (plain(item)) return short(String(item));
  if (!isObj(item)) return Array.isArray(item) ? `${item.length} items` : 'Nothing';
  for (const k of TITLES) if (typeof item[k] === 'string' && item[k]) return short(item[k] as string);
  const shown = Object.entries(item).filter(([k, v]) => plain(v) && !SKIPPED.has(k) && String(v).trim());
  return shown.length ? short(shown.slice(0, 3).map(([k, v]) => `${k} ${v}`).join(' · ')) : 'An item with no fields';
}

/** An item's link, when it has one a person would open. */
export function itemLink(item: unknown): string | null {
  if (!isObj(item)) return null;
  const found = ['html_url', 'htmlLink', 'web_url', 'permalink', 'link'].map((k) => item[k]).find((v) => typeof v === 'string');
  return typeof found === 'string' && /^https?:\/\//.test(found) ? found : null;
}

/** A tool's answer as Pipedream sends it: `{ret, exports}`, its summary in `exports.$summary`. */
export function toolAnswer(value: unknown): { ret: unknown; summary: string | null } | null {
  if (!isObj(value) || !('ret' in value)) return null;
  const exported = isObj(value.exports) ? value.exports.$summary : undefined;
  return { ret: value.ret, summary: typeof exported === 'string' ? exported : null };
}

/** A per-item gate's answer: its outcomes' lists, its decisions and counts. */
export const gateAnswer = (value: unknown): value is Obj => isObj(value) && Array.isArray(value.decisions);

/** The counts a per-item gate's answer gives, as `answer 1 · skip 1`. */
export function gateCounts(value: Obj): string {
  return Object.entries(value)
    .filter(([k, v]) => Array.isArray(v) && k !== 'decisions')
    .map(([k, v]) => `${k} ${(v as unknown[]).length}`)
    .join(' · ');
}

/** The run's output as data when it is JSON, else its text. */
export function parsed(text: string): unknown {
  const t = text.trim();
  if (!t.startsWith('{') && !t.startsWith('[')) return text;
  try {
    return JSON.parse(t);
  } catch {
    return text;
  }
}

/** A plain object's plain fields, as name and text (nested ones by a dotted name), at most 30. */
export function flatFields(value: Obj, at = '', out: Array<[string, string]> = []): Array<[string, string]> {
  for (const [k, v] of Object.entries(value)) {
    if (out.length >= 30) break;
    const name = at ? `${at}.${k}` : k;
    if (plain(v) && String(v).trim()) out.push([name, String(v)]);
    else if (Array.isArray(v) && v.every(plain) && v.length) out.push([name, v.join(', ')]);
    else if (isObj(v)) flatFields(v, name, out);
  }
  return out;
}
