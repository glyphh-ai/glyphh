/**
 * How a bot's cat looks: Spike, the Glyphh cat, in black and white, as the Glyphh Bot app draws him (copied from
 * glyphh-bot src/shared/types.ts, not shared with it). The parts and the pose change from bot to bot; the colours
 * never do.
 */
export type Head = 'classic' | 'spiky' | 'tall' | 'folded' | 'round';
export type Tail = 'spike' | 'bolt' | 'curl' | 'long';
export type Eye = 'dot' | 'side' | 'big' | 'sleepy' | 'heart' | 'star';
export type Extra = 'none' | 'antenna' | 'cape' | 'bolt';
export type Accessory = 'none' | 'headphones' | 'beanie' | 'cap' | 'glasses' | 'shades' | 'bow' | 'scarf' | 'crown' | 'chain';
export type Pose = 'stand' | 'lean' | 'hop' | 'turn';

export const HEADS: Head[] = ['classic', 'spiky', 'tall', 'folded', 'round'];
export const TAILS: Tail[] = ['spike', 'bolt', 'curl', 'long'];
export const EYES: Eye[] = ['dot', 'side', 'big', 'sleepy', 'heart', 'star'];
export const EXTRAS: Extra[] = ['none', 'antenna', 'cape', 'bolt'];
export const ACCESSORIES: Accessory[] = ['none', 'headphones', 'beanie', 'cap', 'glasses', 'shades', 'bow', 'scarf', 'crown', 'chain'];
export const POSES: Pose[] = ['stand', 'lean', 'hop', 'turn'];

export interface Look {
  head: Head;
  tail: Tail;
  eye: Eye;
  extra: Extra;
  accessory: Accessory;
  pose: Pose;
}

/** Any partial or unknown look made whole: unknown parts fall back to Spike's own. */
export function normalizeLook(raw: unknown): Look {
  const l = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const one = <T extends string>(v: unknown, all: T[], d: T): T => (all.includes(v as T) ? (v as T) : d);
  return {
    head: one(l.head, HEADS, 'classic'),
    tail: one(l.tail, TAILS, 'spike'),
    eye: one(l.eye, EYES, 'dot'),
    extra: one(l.extra, EXTRAS, 'none'),
    accessory: one(l.accessory, ACCESSORIES, 'none'),
    pose: one(l.pose, POSES, 'stand'),
  };
}

const pick = <T,>(all: T[]): T => all[Math.floor(Math.random() * all.length)]!;

/** A random cat, for a new bot and the Shuffle button. */
export function randomLook(): Look {
  return { head: pick(HEADS), tail: pick(TAILS), eye: pick(EYES), extra: pick(EXTRAS), accessory: pick(ACCESSORIES), pose: pick(POSES) };
}
