import type { AdaRelease, AdaReleases } from '@/api/ada';
import { date } from './format';

/**
 * Ada's own versions (`GET /v1/ada`) as the pages show them: a name found through its aliases, its status in words,
 * the versions a model may move to, and its release notes as prose.
 */

/** The version a name means, its aliases included (a promoted beta's old name). */
export function releaseOf(releases: AdaReleases | undefined, name: string): AdaRelease | undefined {
  return releases?.versions.find((r) => r.name === name || r.aliases.includes(name));
}

/** A model's Upgrade Ada flow, on its Versions tab, `to` chosen first (none: the latest stable). */
export const upgradePath = (model: string, to = '') => `/models/${encodeURIComponent(model)}?tab=versions&upgrade=${encodeURIComponent(to)}`;

/** An Ada version's notes on the Ada page. */
export const notesPath = (name: string) => `/ada#${encodeURIComponent(name)}`;

/** Whether a name is a beta's: from the registry when it is known, else by its `-beta` ending, as every beta is named. */
export const isBeta = (releases: AdaReleases | undefined, name: string) => releaseOf(releases, name)?.beta ?? name.endsWith('-beta');

/** Stable, Beta, Deprecated with its end, or Retired. */
export function statusText(release: Pick<AdaRelease, 'status' | 'ends'>): string {
  if (release.status === 'stable') return 'Stable';
  if (release.status === 'beta') return 'Beta';
  if (release.status === 'retired') return 'Retired';
  return release.ends ? `Deprecated, ends ${date(release.ends)}` : 'Deprecated';
}

/**
 * The versions a model on `current` may move to, newest first: a stable or a beta still open; never a deprecated or
 * retired one, nor the one it runs. Older ones are offered too (a downgrade).
 */
export function targetsFor(releases: AdaReleases, current: string): AdaRelease[] {
  const on = releaseOf(releases, current)?.name ?? current;
  return releases.versions.filter((r) => r.name !== on && (r.status === 'stable' || (r.status === 'beta' && r.open)));
}

/** The target offered first: the latest stable, unless the model runs it already. */
export function defaultTarget(releases: AdaReleases, current: string): string {
  const targets = targetsFor(releases, current);
  return (targets.find((r) => r.name === releases.latest_stable) ?? targets[0])?.name ?? '';
}

/** The versions a new model may be made on: every stable and open beta. */
export const choosable = (releases: AdaReleases) => releases.versions.filter((r) => r.status === 'stable' || (r.status === 'beta' && r.open));

/** A version in a list to choose from: `ada-1-0 (latest stable)`, `ada-1-1-beta (Beta)`, or an older one by its name. */
export function optionText(release: AdaRelease, releases: AdaReleases): string {
  if (release.name === releases.latest_stable) return `${release.name} (latest stable)`;
  if (release.beta) return `${release.name} (Beta)`;
  return release.name;
}

/** A part of a line of notes: plain, **bold** or `code`. */
export type Inline = { kind: 'text' | 'bold' | 'code'; text: string };
/** A paragraph of notes, or a list from its `- ` lines. */
export type NotesBlock = { kind: 'p'; text: string } | { kind: 'list'; items: string[] };

/** Release notes as the registry writes them: paragraphs apart by a blank line, a line starting `- ` an item of a list. */
export function notesBlocks(notes: string): NotesBlock[] {
  const blocks: NotesBlock[] = [];
  for (const chunk of notes.replace(/\r\n/g, '\n').split(/\n\s*\n/)) {
    let words: string[] = [];
    let items: string[] | null = null;
    const endParagraph = () => {
      if (words.length) blocks.push({ kind: 'p', text: words.join(' ') });
      words = [];
    };
    for (const raw of chunk.split('\n')) {
      const line = raw.trim();
      if (!line) continue;
      if (/^[-*] /.test(line)) {
        endParagraph();
        if (!items) blocks.push({ kind: 'list', items: (items = []) });
        items.push(line.slice(2).trim());
      } else if (items && /^\s/.test(raw)) {
        // An item's text carried on to an indented line.
        items[items.length - 1] += ` ${line}`;
      } else {
        items = null;
        words.push(line);
      }
    }
    endParagraph();
  }
  return blocks;
}

/** A line's **bold** and `code`, apart from its plain text. */
export function inlineParts(text: string): Inline[] {
  const parts: Inline[] = [];
  let last = 0;
  for (const match of text.matchAll(/\*\*([^*]+)\*\*|`([^`]+)`/g)) {
    if (match.index > last) parts.push({ kind: 'text', text: text.slice(last, match.index) });
    parts.push(match[1] !== undefined ? { kind: 'bold', text: match[1] } : { kind: 'code', text: match[2]! });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ kind: 'text', text: text.slice(last) });
  return parts;
}
