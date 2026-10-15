export type Frame = { contentWindow: unknown; remove(): void }
export type Means = {
  frame(html: string): Frame
  later(ms: number, fn: () => void): unknown
  cancel(timer: unknown): void
  loopClosed(effect: string): void
}
export type Play = { kind: 'one-shot' | 'loop'; effect: string; html: string; closeAfterMs: number }

export const DRIP_Z: number
export const CLOSE_SIGNAL: string
export function makeFrame(doc: unknown, html: string): Frame
export function createRunner(means: Means): {
  play(p: Play): void
  close(effect: string): void
  stopAll(): void
  message(source: unknown, data: unknown): void
  loopsPlaying(): number
}
