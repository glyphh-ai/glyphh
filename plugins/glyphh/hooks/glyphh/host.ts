// What the account code may do, handed to it by index.tsx. The engine's scan
// follows `$` only inside the file that received it, and reads state only
// through atoms declared beside the call; so every `$` call and atom lives in
// index.tsx, and the modules here work on this interface. (It also makes them
// plain to test.)
import type { FsEntry, HttpInit, HttpResponse, McpToolResult, ProcessRunInit, ProcessRunResult, RenderSurface, Timer } from 'claude-code'

import type { AuthState, GlyphhNote, GlyphhSection, Json } from '../../types'

/** One state value: read it, or change it from what it is. */
export type Value<T> = { get(): Promise<T>; set(fn: (v: T) => T): Promise<void> }

export type Host = {
  env: { home(): Promise<string | undefined>; server(): Promise<string | undefined> }
  http: { fetch(url: string, init?: HttpInit): Promise<HttpResponse> }
  fs: {
    read(path: string): Promise<string>
    write(path: string, text: string): Promise<void>
    exists(path: string): Promise<boolean>
    list(path: string): Promise<FsEntry[]>
  }
  process: { run(argv: readonly string[], init?: ProcessRunInit): Promise<ProcessRunResult> }
  clock: { now(): Promise<number>; after(ms: number, fn: () => void): Timer }
  store: { get(key: string): Promise<unknown>; set(key: string, value: unknown): Promise<void> }
  mcp: { call(server: string, tool: string, args?: Record<string, unknown>): Promise<McpToolResult> }
  surface(): Promise<RenderSurface | null>
  copy(text: string, surface?: RenderSurface): Promise<boolean>
  /** Opens the Glyphh panel; false where no surface could place it. */
  openPanel(): Promise<boolean>
  /** Asks Claude, as a prompt in the chat (a turn). */
  ask(text: string): Promise<void>
  pluginRoot: string
  state: {
    auth: Value<AuthState>
    section: Value<GlyphhSection>
    me: Value<Json | null>
    lists: Value<Record<string, Json[]>>
    note: Value<GlyphhNote | null>
    inviteLink: Value<string | null>
  }
}
