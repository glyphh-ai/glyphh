// Effects in Claude's window: the Drips page, a local page in the desktop
// app's Browser pane, plays them in sandboxed frames over itself (the Glyphh
// app's web runner). Opening the page: in the Browser pane by
// Claude_Browser's preview_start; where the app refuses that call, Claude is
// asked to open it, with a one-time address only; outside the desktop app,
// in the person's own browser. Works on PageDeps, closures over `$` that
// ./hooks.tsx hands it.
import type { McpToolResult } from 'claude-code'

import { loopDoc, oneShotDoc } from './docs.ts'
import type { Link, Viewport } from './link.ts'
import type { Closer, Host } from './manager.ts'

/** One state value: read it, or change it from what it is. */
export type Value<T> = { get(): Promise<T>; set(fn: (v: T) => T): Promise<void> }

export type PageDeps = {
  isDesktop(): Promise<boolean>
  mcp(server: string, tool: string, args: Record<string, unknown>): Promise<McpToolResult>
  /** Opens an address in the person's default browser; false when it could not. */
  openExternal(url: string): Promise<boolean>
  /** Asks Claude, as a prompt of its own once the command in progress is done. */
  ask(text: string): void
  sleep(ms: number): Promise<void>
  /** The running helper, started when it is not. */
  link(): Promise<Link>
  /** The Browser pane's tab that shows the page. */
  tab: Value<string | null>
}

export type Shown = 'open' | 'opened' | 'asked' | 'external'

/** Before the page has said how large it is. */
export const DEFAULT_VIEWPORT: Viewport = { w: 1280, h: 800 }
/** How long a play waits for a page it opened to come up. */
export const OPEN_WAIT_MS = 8_000
const POLL_MS = 200

const textOf = (r: McpToolResult) => r.content.map(b => b.text ?? '').join('\n')

async function browser(d: PageDeps, tool: string, args: Record<string, unknown>): Promise<string> {
  const r = await d.mcp('Claude_Browser', tool, args)
  if (r.isError) throw new Error(textOf(r) || `${tool} failed`)
  return textOf(r)
}

/** The page on screen: already open (its tab brought to the front), opened, or asked for. */
export async function showPage(d: PageDeps): Promise<Shown> {
  const link = await d.link()
  const desktop = await d.isDesktop()
  const known = await d.tab.get()
  if ((await link.state()).open > 0) {
    if (desktop && known) await d.mcp('Claude_Browser', 'tabs_select', { tabId: known }).catch(() => undefined)
    return 'open'
  }
  const url = await link.pageUrl()
  if (!desktop) {
    if (await d.openExternal(url)) return 'external'
    throw new Error(`Open this page in your browser (it opens once): ${url}`)
  }
  if (known) await d.mcp('Claude_Browser', 'tabs_close', { tabId: known }).catch(() => undefined)
  try {
    const text = await browser(d, 'preview_start', { url })
    const tab = /"tabId":\s*"([^"]+)"/.exec(text)?.[1] ?? null
    await d.tab.set(() => tab)
    return 'opened'
  } catch {
    await d.tab.set(() => null)
    d.ask(`Open this page in the browser pane (it opens once): ${url}`)
    return 'asked'
  }
}

export function shownText(how: Shown): string {
  if (how === 'asked') return 'Drips page: Claude is asked to open it'
  if (how === 'external') return 'Drips page: opened in your browser'
  return 'Drips page ✓'
}

/** The page open and its size, for playing: opened first when it is not. */
export async function readyPage(d: PageDeps): Promise<{ link: Link; viewport: Viewport }> {
  const how = await showPage(d)
  if (how === 'asked') throw new Error('The Drips page is opening in the browser pane: play again once it shows.')
  const link = await d.link()
  let state = await link.state()
  for (let waited = 0; state.open === 0 && how !== 'open' && waited < OPEN_WAIT_MS; waited += POLL_MS) {
    await d.sleep(POLL_MS)
    state = await link.state()
  }
  if (state.open === 0) throw new Error('The Drips page did not open: run /drips, then play again.')
  return { link, viewport: state.viewport ?? DEFAULT_VIEWPORT }
}

export type WindowHost = Host & {
  /** The page ended a looping effect by itself (its time ran out, or Esc). */
  closed(effect: string): void
}

export function windowHost(d: PageDeps): WindowHost {
  const loops = new Map<string, () => void>()
  return {
    async oneShot(effect, opacity) {
      const { link, viewport } = await readyPage(d)
      await link.play({ kind: 'one-shot', effect, ...oneShotDoc(effect, viewport.w, viewport.h, opacity) })
    },
    async persistent(effect, opacity, maxMs, onClosed): Promise<Closer> {
      const { link, viewport } = await readyPage(d)
      await link.play({ kind: 'loop', effect, ...loopDoc(effect, viewport.w, viewport.h, opacity, maxMs) })
      loops.set(effect, onClosed)
      return {
        close: async () => {
          if (loops.get(effect) !== onClosed) return
          loops.delete(effect)
          await link.close(effect)
        },
      }
    },
    closed(effect) {
      const onClosed = loops.get(effect)
      loops.delete(effect)
      onClosed?.()
    },
  }
}
