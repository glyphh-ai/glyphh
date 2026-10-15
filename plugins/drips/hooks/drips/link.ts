// The Drips page's helper (helper/server.mjs) as the mod sees it: the
// requests the mod makes of it (with the token), and the messages the page
// leaves for the mod.
import type { CustomDrip, Display } from '../../types'

export type Viewport = { w: number; h: number }

export type HelperState = { version: string; open: number; viewport: Viewport | null }

/** What the page draws: the saved recipes, the effects to pick from, where effects play. */
export type PageLibrary = { drips: CustomDrip[]; effects: string[]; display: Display }

/** An effect for the page to play in its window. */
export type PagePlay = { kind: 'one-shot' | 'loop'; effect: string; html: string; closeAfterMs: number }

/** What the page asks of the mod. */
export type PageMessage =
  | { t: 'play'; recipe: string }
  | { t: 'stop' }
  | { t: 'save'; name: string; recipe: string; original: string | null }
  | { t: 'delete'; name: string }
  | { t: 'closed'; effect: string }

const str = (v: unknown): v is string => typeof v === 'string'

/** One of the page's messages, if it is one. */
export function parseMessage(raw: unknown): PageMessage | null {
  const m = raw as Record<string, unknown> | null
  if (!m || typeof m !== 'object') return null
  if (m.t === 'play' && str(m.recipe)) return { t: 'play', recipe: m.recipe }
  if (m.t === 'stop') return { t: 'stop' }
  if (m.t === 'save' && str(m.name) && str(m.recipe)) return { t: 'save', name: m.name, recipe: m.recipe, original: str(m.original) ? m.original : null }
  if (m.t === 'delete' && str(m.name)) return { t: 'delete', name: m.name }
  if (m.t === 'closed' && str(m.effect)) return { t: 'closed', effect: m.effect }
  return null
}

function parseViewport(v: unknown): Viewport | null {
  const o = v as Record<string, unknown> | null
  return o && typeof o.w === 'number' && typeof o.h === 'number' && o.w > 0 && o.h > 0 ? { w: o.w, h: o.h } : null
}

export type Fetch = (url: string, init: { method: string; headers: Record<string, string>; body?: string }) => Promise<{ ok: boolean; text: string }>

export type Link = {
  state(): Promise<HelperState>
  /** A one-time address that opens the page. */
  pageUrl(): Promise<string>
  library(lib: PageLibrary): Promise<void>
  play(p: PagePlay): Promise<void>
  /** Ends a looping effect in the page. */
  close(effect: string): Promise<void>
  /** Ends every looping effect in the page. */
  stop(): Promise<void>
  /** The page's messages; asking keeps the helper alive. */
  inbox(): Promise<PageMessage[]>
  quit(): Promise<void>
}

export function linkTo(fetch: Fetch, port: number, token: string): Link {
  const base = `http://127.0.0.1:${port}`
  const ask = async (path: string, body?: unknown): Promise<Record<string, unknown>> => {
    const res = await fetch(`${base}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'X-Token': token, 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!res.ok) throw new Error(`the Drips page answered ${path} with an error`)
    return JSON.parse(res.text) as Record<string, unknown>
  }
  return {
    state: async () => {
      const s = await ask('/api/state')
      return { version: String(s.version ?? ''), open: Number(s.open) || 0, viewport: parseViewport(s.viewport) }
    },
    pageUrl: async () => `${base}/?k=${String((await ask('/api/key', {})).key)}`,
    library: async lib => void (await ask('/api/library', lib)),
    play: async p => void (await ask('/api/play', p)),
    close: async effect => void (await ask('/api/close', { effect })),
    stop: async () => void (await ask('/api/stop', {})),
    inbox: async () => (((await ask('/api/inbox')).messages as unknown[] | undefined) ?? []).flatMap(m => parseMessage(m) ?? []),
    quit: async () => void (await ask('/api/quit', {})),
  }
}

/** The helper's files: a change to any of them makes a new helper. */
export const HELPER_FILES = ['server.mjs', 'gate.mjs', 'page.html', 'page.css', 'page.js', 'builder.mjs', 'runner.mjs']

/** A version for the helper's code: a digest of its files' texts. */
export async function versionOf(texts: string[]): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texts.join('\u0000')))
  return Array.from(new Uint8Array(digest).slice(0, 8), b => b.toString(16).padStart(2, '0')).join('')
}
