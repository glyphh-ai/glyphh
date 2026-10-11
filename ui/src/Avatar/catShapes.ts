/** The Glyphh cat's shapes, ported from the old app's avatar (bot-avatar.ts), 165×200 box.
 *  Every face is the mascot with one or two parts changed. */

export type Ear = "classic" | "tall" | "folded" | "round" | "spiky";
export type Eye = "classic" | "look" | "up" | "big" | "sleepy" | "wink" | "star";
export type Tail = "classic" | "bolt" | "curl" | "long";
export type Extra = "none" | "antenna" | "cape" | "bolt";
export interface Parts { ear: Ear; eye: Eye; tail: Tail; extra: Extra }
export type Mood = "idle" | "thinking" | "generating" | "done" | "listening" | "error" | "curious" | "sleepy" | "playful" | "dizzy";

const BASE: Parts = { ear: "classic", eye: "classic", tail: "classic", extra: "none" };

export const VARIANTS: ReadonlyArray<{ id: number; name: string; parts: Partial<Parts> }> = [
  { id: 1, name: "Glyphh", parts: {} }, { id: 2, name: "Side-eye", parts: { eye: "look" } },
  { id: 3, name: "Big eye", parts: { eye: "big" } }, { id: 4, name: "Sleepy", parts: { eye: "sleepy" } },
  { id: 5, name: "Wink", parts: { eye: "wink" } }, { id: 6, name: "Star eye", parts: { eye: "star" } },
  { id: 7, name: "Tall ears", parts: { ear: "tall" } }, { id: 8, name: "Folded ear", parts: { ear: "folded" } },
  { id: 9, name: "Spiky", parts: { ear: "spiky" } }, { id: 10, name: "Round ears", parts: { ear: "round" } },
  { id: 11, name: "Bolt tail", parts: { tail: "bolt" } }, { id: 12, name: "Curl tail", parts: { tail: "curl" } },
  { id: 13, name: "Long tail", parts: { tail: "long" } }, { id: 14, name: "Antenna", parts: { extra: "antenna" } },
  { id: 15, name: "Cape", parts: { extra: "cape" } }, { id: 16, name: "Bolt mark", parts: { extra: "bolt" } },
];

/** A mood changes the eye; idle keeps the face's own. */
const MOOD_EYE: Record<Mood, Eye | null> = {
  idle: null, thinking: "up", generating: "big", done: "wink", listening: "big",
  error: "sleepy", curious: "look", sleepy: "sleepy", playful: "wink", dizzy: "star",
};

const EARS: Record<Ear, { right: string; left: string }> = {
  classic: { right: "L135 13 L123 57", left: "M28 15 L62 42 L39 54 Z" },
  tall: { right: "L138 9 L123 57", left: "M22 9 L62 42 L39 54 Z" },
  folded: { right: "L110 26 L138 26 L123 57", left: "M28 15 L62 42 L39 54 Z" },
  round: { right: "C106 14 142 6 123 57", left: "M36 20 C26 32 32 50 39 54 L62 42 C56 30 48 18 36 20 Z" },
  spiky: { right: "L99 10 L111 34 L135 13 L123 57", left: "M28 15 L62 42 L39 54 Z" },
};

const TAILS: Record<Tail, string> = {
  classic: "L112 150 C126 152 136 151 145 149 C137 158 130 164 124 169",
  bolt: "L112 148 L136 140 L128 152 L152 146 L126 168",
  curl: "L112 150 C132 150 150 140 146 126 C143 138 132 158 124 169",
  long: "L112 150 C130 152 150 150 160 140 C150 160 134 166 124 169",
};

export interface Cat { id: number; name: string; parts: Parts; eye: Eye; body: string; leftEar: string }

/** The cat for a face (1–16; anything else is Glyphh) in a mood. */
export function catOf(variant: number, mood: Mood): Cat {
  const face = VARIANTS.find((v) => v.id === variant) ?? (VARIANTS[0] as (typeof VARIANTS)[number]);
  const parts: Parts = { ...BASE, ...face.parts };
  const ear = EARS[parts.ear];
  const body = `M40 62 ${ear.right} C140 70 144 104 128 121 L112 133 ${TAILS[parts.tail]} L128 179 L35 180 L44 131 C18 118 20 80 40 62 Z`;
  return { id: face.id, name: face.name, parts, eye: MOOD_EYE[mood] ?? parts.eye, body, leftEar: ear.left };
}
