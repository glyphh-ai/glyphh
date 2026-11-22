import type { Look } from './look';

/**
 * Glyphh's own cats, the Glyphh Bot app's crew (glyphh-bot src/main/store.ts), each Spike in black and white with
 * parts of their own: the mascots a bot can be, beside Shuffle and one drawn from words.
 */
export const MASCOTS: ReadonlyArray<{ name: string; tagline: string; look: Look }> = [
  { name: 'Juno', tagline: 'Makes it look right', look: { head: 'tall', tail: 'curl', eye: 'heart', extra: 'none', accessory: 'bow', pose: 'lean' } },
  { name: 'Dex', tagline: 'Ships before lunch', look: { head: 'spiky', tail: 'bolt', eye: 'big', extra: 'bolt', accessory: 'headphones', pose: 'hop' } },
  { name: 'Rio', tagline: 'Reads the docs', look: { head: 'round', tail: 'long', eye: 'side', extra: 'antenna', accessory: 'glasses', pose: 'turn' } },
  { name: 'Koda', tagline: 'Will find the bug', look: { head: 'folded', tail: 'spike', eye: 'sleepy', extra: 'none', accessory: 'shades', pose: 'stand' } },
  { name: 'Mika', tagline: 'Keeps the plan', look: { head: 'classic', tail: 'curl', eye: 'star', extra: 'cape', accessory: 'scarf', pose: 'stand' } },
];

const same = (a: Partial<Look>, b: Look) => (Object.keys(b) as (keyof Look)[]).every((k) => a[k] === b[k]);

/** The crew cat a look is, if it is one. */
export const mascotOf = (look: Partial<Look> | null | undefined) => (look ? MASCOTS.find((m) => same(look, m.look)) : undefined);

/** A drawn mascot as an image source: shown as an image, never as markup, so nothing in it can run. */
export const mascotSrc = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
