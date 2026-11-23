// What a bot's turn says, worked out from its run: clean words first (the bot's own answer, or the server's plain
// summary of what happened), then what its steps brought back that a person can look at (images, files). Raw JSON and
// engine log lines are never the answer: they stay behind the turn's "Ran N steps" line and its Raw toggle.
import type { BotRun, BotSpec } from '@/api/bots';

/** True for text that is a JSON object or array: a step's data, not words for a person. */
export function isJson(text: string): boolean {
  const t = text.trim();
  if (!t || !/^[[{]/.test(t)) return false;
  try {
    const v: unknown = JSON.parse(t);
    return typeof v === 'object' && v !== null;
  } catch {
    return false;
  }
}

/** A run's own answer when it is prose; a structured answer is not shown as words. */
export const prose = (output: string | null | undefined): string => (output && !isJson(output) ? output.trim() : '');

const sentence = (s: string): string => {
  const t = s.trim().replace(/[\s:;,]+$/, '');
  if (!t) return '';
  return t[0]!.toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? '' : '.');
};

const named = (id: string): string => id.replace(/[_-]+/g, ' ').trim();

/** The runner's own words for things, said plainly: what it calls a gate is a decision. */
export const plainWords = (text: string): string => text.replace(/\bgates\b/gi, 'decisions').replace(/\bgate\b/gi, 'decision').replace(/\bloop\b/gi, 'steps');

/** The runner's reason as a sentence: its line ("… today 0, later 0; the run ends here") never reaches a person as is. */
export function plainReason(reason: string): string {
  const cut = reason.replace(/[:;,]?\s*the run ends here\.?\s*$/i, '').trim();
  const one = /^gate (\S+) said (\S+)$/i.exec(cut);
  if (one) return `It decided ${named(one[2]!)} on ${named(one[1]!)}, so it stopped there.`;
  const each = /^gate \S+: (.*)$/i.exec(cut);
  if (each) {
    const counts = [...each[1]!.matchAll(/(\d+)/g)].reduce((n, m) => n + Number(m[1]), 0);
    return counts === 0 ? 'There was nothing to decide, so it stopped there.' : `It decided ${counts} (${named(each[1]!)}), so it stopped there.`;
  }
  const req = /^(\S+) requires /i.exec(cut);
  if (req) return `${sentence(named(req[1]!)).slice(0, -1)} had nothing to work on, so it stopped there.`;
  return sentence(plainWords(cut.replace(/^the program ended the run:\s*/i, '')));
}

/**
 * What happened, in words, when the server did not say (`summary`, an older server): the same sentences it would
 * write, from the run's state and its engine reason.
 */
export function fallbackSummary(run: BotRun): string {
  if (run.status === 'needs_input') return run.question ? '' : 'Waiting on your answer.';
  if (run.status === 'skipped') return run.error ? `It did not run: ${sentence(plainWords(run.error))}` : 'It did not run.';
  if (run.status === 'failed') {
    if (run.error === 'cancelled') return 'Cancelled before it finished.';
    if (/interrupted by a restart/.test(run.error)) return 'It was cut off by a restart before it finished. Run it again.';
    return run.error ? `It failed: ${sentence(plainWords(run.error))}` : 'It failed.';
  }
  if (run.status !== 'done') return '';
  return run.error ? plainReason(run.error) : 'It finished.';
}

/**
 * The bot's own words in a run: its answer when that is prose, else what the last of its Claude steps wrote (a run
 * that ends by posting or filing answers with that tool's data, which is not words).
 */
export function answerOf(run: BotRun, spec?: BotSpec): string {
  const own = prose(run.output);
  if (own || run.status !== 'done' || run.error) return own;
  const wrote = (spec?.loop ?? []).filter((s) => typeof s.agent === 'string' && typeof s.id === 'string').map((s) => run.data?.[s.id as string]);
  return prose(wrote.filter((v): v is string => typeof v === 'string').at(-1));
}

/** The turn's words: the bot's own answer and, beside or instead of it, what happened and what the bot takes. */
export function wordsOf(run: BotRun, spec?: BotSpec): { answer: string; summary: string; hint: string } {
  const answer = answerOf(run, spec);
  const said = (run.summary ?? fallbackSummary(run)).trim();
  // A run that went the whole way with an answer of its own needs no "It finished all 4 steps" beside it; a
  // question is asked in the turn itself.
  const whole = run.status === 'done' && !run.error;
  const asked = run.status === 'needs_input' && run.question !== null;
  return { answer, summary: (answer && whole) || asked ? '' : said, hint: (run.hint ?? '').trim() };
}

export type Shot = { src: string; alt: string };
export type FileChip = { name: string; size: number | null; url: string | null; did?: string };

const IMAGE_URL = /^https?:\/\/[^\s]+\.(png|jpe?g|gif|webp)(\?[^\s]*)?$/i;
const IMAGE_KEYS = /^(image|image_url|imageUrl|thumbnail_url|picture|photo_url|screenshot|screenshot_url)$/;
const IMAGE_MIME = /^image\/(png|jpe?g|gif|webp)$/i;
const web = (v: unknown): v is string => typeof v === 'string' && /^https?:\/\//i.test(v);
export const isImageName = (name: string): boolean => /\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(name);

function walk(value: unknown, visit: (key: string, v: unknown) => void, depth = 0, key = ''): void {
  visit(key, value);
  if (depth >= 5 || value === null || typeof value !== 'object') return;
  if (Array.isArray(value)) return value.slice(0, 40).forEach((v) => walk(v, visit, depth + 1, key));
  for (const [k, v] of Object.entries(value)) if (!k.startsWith('_')) walk(v, visit, depth + 1, k);
}

/** A run's own steps' data: everything but what it was given and the engine's own notes. */
const stepData = (run: BotRun): unknown[] => Object.entries(run.data ?? {}).filter(([k]) => k !== 'input' && !k.startsWith('_')).map(([, v]) => v);

/**
 * Images its steps brought back: an MCP image block (`{type: "image", data, mimeType}`), an image URL, or a URL under
 * an image's key. The web and data: images only, each once, six at most, none the answer's own markdown already shows.
 */
export function imagesOf(run: BotRun, shown = ''): Shot[] {
  const out: Shot[] = [];
  const add = (src: string, alt: string) => {
    if (out.length < 6 && !out.some((s) => s.src === src) && !shown.includes(src)) out.push({ src, alt });
  };
  for (const data of stepData(run))
    walk(data, (key, v) => {
      if (typeof v === 'string') {
        if (web(v) && (IMAGE_URL.test(v) || IMAGE_KEYS.test(key))) add(v, key || 'image');
        return;
      }
      const block = v as { type?: unknown; data?: unknown; mimeType?: unknown; alt?: unknown } | null;
      if (block && block.type === 'image' && typeof block.data === 'string' && typeof block.mimeType === 'string' && IMAGE_MIME.test(block.mimeType))
        add(`data:${block.mimeType};base64,${block.data}`, typeof block.alt === 'string' ? block.alt : 'image');
    });
  return out;
}

/**
 * The run's files, six at most: first those of its own folders it read and changed (the server names them, with what
 * it did: "read", "written", "moved"), then files its steps name (an attachment, a document: a name with a size or a type).
 */
export function filesOf(run: BotRun): FileChip[] {
  const out: FileChip[] = [];
  for (const f of run.files ?? []) if (out.length < 6 && !out.some((o) => o.name === f.name)) out.push({ name: f.name, size: null, url: null, did: f.did });
  for (const data of stepData(run))
    walk(data, (_key, v) => {
      if (v === null || typeof v !== 'object' || Array.isArray(v)) return;
      const f = v as Record<string, unknown>;
      const name = typeof f.filename === 'string' ? f.filename : typeof f.name === 'string' && (typeof f.mimeType === 'string' || typeof f.mime_type === 'string' || typeof f.size === 'number') ? f.name : '';
      if (!name || out.length >= 6 || out.some((o) => o.name === name)) return;
      const url = [f.webViewLink, f.html_url, f.url, f.link].find(web) ?? null;
      out.push({ name, size: typeof f.size === 'number' ? f.size : null, url });
    });
  return out;
}

export function fileSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** A short type label for a file card. */
export function fileKind(name: string): string {
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';
  return ext ? ext.slice(0, 4).toUpperCase() : 'FILE';
}

/** A link card's badge: the kind the server names, as four mono capitals at most. */
export const linkBadge = (kind: string): string =>
  ({ 'Pull request': 'PR', Issue: 'ISS', GitHub: 'GIT', Slack: 'SLK', Doc: 'DOC', Notion: 'NOTE', Linear: 'LIN', App: 'APP' })[kind] ?? 'LINK';

/** Where a link goes, short: its host and path without the scheme. */
export function linkWhere(url: string): string {
  try {
    const u = new URL(url);
    return (u.host.replace(/^www\./, '') + u.pathname).replace(/\/$/, '');
  } catch {
    return url;
  }
}
