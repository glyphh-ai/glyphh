// The fullscreen overlay's command protocol (native/overlay.swift), pure.
//
//   drips-overlay screen   prints the screen under the cursor, one JSON line:
//                          {"x":0,"y":0,"w":1512,"h":982} (points, AppKit's
//                          global coordinates)
//   drips-overlay play     reads one PlayRequest as JSON on stdin, opens a
//                          transparent, click-through window over that screen
//                          showing the document, and prints one JSON line per
//                          event: {"t":"shown","pid":123} once on screen, then
//                          {"t":"closed","why":"signal"|"timeout"|"term"|"orphan"}
//                          as it exits; {"t":"error","message":"..."} when it
//                          cannot. It closes on the document's __drip_close__,
//                          after closeAfterMs (clamped to OVERLAY_CAP_MS), on
//                          SIGTERM, or when its parent is gone.

export const PROTOCOL_VERSION = 1
/** The overlay never stays longer than this, whatever it is asked. */
export const OVERLAY_CAP_MS = 30 * 60_000
export const OVERLAY_MIN_MS = 100

export type Screen = { x: number; y: number; w: number; h: number }
export type PlayRequest = { v: typeof PROTOCOL_VERSION; html: string; screen: Screen; closeAfterMs: number }
export type CloseReason = 'signal' | 'timeout' | 'term' | 'orphan'
export type OverlayEvent = { t: 'shown'; pid: number } | { t: 'closed'; why: CloseReason } | { t: 'error'; message: string }

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

/** The screen the overlay printed, if it is one. */
export function parseScreen(text: string): Screen | null {
  try {
    const s = JSON.parse(text.trim()) as Record<string, unknown>
    if (!isNum(s.x) || !isNum(s.y) || !isNum(s.w) || !isNum(s.h) || s.w <= 0 || s.h <= 0) return null
    return { x: s.x, y: s.y, w: s.w, h: s.h }
  } catch {
    return null
  }
}

export const clampMs = (ms: number) => Math.min(OVERLAY_CAP_MS, Math.max(OVERLAY_MIN_MS, Number.isFinite(ms) ? Math.round(ms) : OVERLAY_CAP_MS))

/** What `play` reads on stdin. */
export function playRequest(html: string, screen: Screen, closeAfterMs: number): string {
  const req: PlayRequest = { v: PROTOCOL_VERSION, html, screen, closeAfterMs: clampMs(closeAfterMs) }
  return JSON.stringify(req)
}

const REASONS: readonly CloseReason[] = ['signal', 'timeout', 'term', 'orphan']

/** One line the overlay printed, if it is an event. */
export function parseEvent(line: string): OverlayEvent | null {
  try {
    const m = JSON.parse(line) as Record<string, unknown>
    if (m.t === 'shown' && isNum(m.pid) && m.pid > 0) return { t: 'shown', pid: m.pid }
    if (m.t === 'closed' && REASONS.includes(m.why as CloseReason)) return { t: 'closed', why: m.why as CloseReason }
    if (m.t === 'error' && typeof m.message === 'string') return { t: 'error', message: m.message }
    return null
  } catch {
    return null
  }
}

/** Splits text that arrives in pieces into whole lines. */
export function lineSplitter(): (piece: string) => string[] {
  let rest = ''
  return piece => {
    const parts = (rest + piece).split('\n')
    rest = parts.pop() ?? ''
    return parts.map(l => l.trim()).filter(Boolean)
  }
}

/** Where the compiled overlay is kept: one binary per version of its source. */
export const binaryPath = (home: string, digest: string) => `${home.replace(/\/$/, '')}/Library/Caches/glyphh-drips/drips-overlay-${digest}`

export const compileArgv = (swiftc: string, source: string, out: string): string[] => [
  swiftc,
  '-O',
  '-o',
  out,
  source,
  '-framework',
  'AppKit',
  '-framework',
  'WebKit',
]

/** A short digest of a text: names the binary built from it. */
export async function digestOf(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(digest).slice(0, 8), b => b.toString(16).padStart(2, '0')).join('')
}
