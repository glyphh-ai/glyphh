// A Host in memory: files, a clock that moves when told, the browser pane's
// tool, and the fake server for HTTP. What the account code sees of the world.
import type { FsEntry, McpToolResult, RenderSurface } from 'claude-code'

import type { Host, Value } from '../hooks/glyphh/host'
import { fakeServer } from './fake-server'

export const HOME = '/home/t'

function value<T>(initial: T): Value<T> {
  let v = initial
  return {
    get: async () => v,
    set: async fn => {
      v = fn(v)
    },
  }
}

/** Lets started work run its course (it awaits only this fake world). */
export async function settle() {
  for (let i = 0; i < 2000; i++) await Promise.resolve()
}

export const MACHINE_UUID = '0A1B2C3D-0000-4000-8000-00000000F00D'
const IOREG = `+-o J316sAP  <class IOPlatformExpertDevice>\n    "IOPlatformUUID" = "${MACHINE_UUID}"\n`
const done = (stdout = '') => ({ exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })

/** Files in a map; the shell writer (umask 077) marks its file 0600. */
function fakeFiles() {
  const files = new Map<string, string>()
  const modes = new Map<string, string>()
  const argvs: string[][] = []
  const run = async (argv: readonly string[], init?: { stdin?: string }) => {
    argvs.push([...argv])
    if (argv[0] === '/usr/sbin/ioreg') return done(IOREG)
    if (argv[0] === '/bin/sh' && argv.length > 5) {
      files.set(argv[5]!, init?.stdin ?? '')
      modes.set(argv[5]!, '600')
    } else if (argv[0] === '/bin/rm') files.delete(argv[2]!)
    return done(argv[0] === 'hostname' ? 'testmac\n' : '')
  }
  const fs: Host['fs'] = {
    read: async p => {
      const t = files.get(p)
      if (t === undefined) throw new Error(`ENOENT ${p}`)
      return t
    },
    // A binary file is kept as its bytes' characters; the engine's `{ as: 'bytes' }` read answers base64.
    readBytes: async p => {
      const t = files.get(p)
      if (t === undefined) throw new Error(`ENOENT ${p}`)
      return btoa(t)
    },
    write: async (p, t) => void files.set(p, t),
    exists: async p => files.has(p) || [...files.keys()].some(k => k.startsWith(`${p}/`)),
    list: async (dir): Promise<FsEntry[]> =>
      [...files.keys()]
        .filter(p => p.startsWith(`${dir}/`) && !p.slice(dir.length + 1).includes('/'))
        .map(p => ({ name: p.slice(dir.length + 1), kind: 'file' as const, size: 1, mtimeMs: 0, isLink: false })),
  }
  return { files, modes, argvs, fs, run }
}

/** A clock that moves only on `advance`, firing the timers due. */
function fakeClock() {
  let now = Date.parse('2026-10-13T12:00:00Z')
  let timers: { at: number; fn: () => void; dead: boolean }[] = []
  const clock: Host['clock'] = {
    now: async () => now,
    after: (ms, fn) => {
      const t = { at: now + ms, fn, dead: false }
      timers.push(t)
      return { cancel: () => void (t.dead = true) } as ReturnType<Host['clock']['after']>
    },
  }
  async function advance(ms: number) {
    now += ms
    for (let due = timers.find(t => !t.dead && t.at <= now); due; due = timers.find(t => !t.dead && t.at <= now)) {
      due.dead = true
      due.fn()
      await settle()
    }
    timers = timers.filter(t => !t.dead)
  }
  return { clock, advance }
}

const freshState = (): Host['state'] => ({
  auth: value({ status: 'out' }),
  section: value('account'),
  me: value(null),
  lists: value({}),
  note: value(null),
  inviteLink: value(null),
  apps: value({ q: '', page: 1, state: 'approved', type: '', total: 0, rejecting: null }),
  dip: value({ layouts: [], active: null, draft: null, note: null }),
})

/** The desktop app's tools as /dip calls them: each call kept, the browser's tabs in a list, `refuse` the tools
 *  that answer a refusal. */
function fakeTools(refuse: string[]) {
  const calls: { tool: string; input: Record<string, unknown> }[] = []
  const tabs: { tabId: string; url: string; isActive: boolean }[] = []
  let n = 0
  const call = async (tool: string, input: Record<string, unknown>) => {
    calls.push({ tool, input })
    if (refuse.includes(tool)) return { ok: false, text: 'refused' }
    const short = tool.replace(/^mcp__[^_]+(?:_[^_]+)*__/, '')
    if (short === 'preview_start') {
      for (const t of tabs) t.isActive = false
      tabs.push({ tabId: `t${++n}`, url: String(input.url), isActive: true })
    } else if (short === 'tabs_close') {
      tabs.splice(tabs.findIndex(t => t.tabId === input.tabId) >>> 0, 1)
    } else if (short === 'tabs_context') {
      // As the app answers: the JSON, then a sentence that itself holds braces.
      const json = JSON.stringify({ browserOpen: true, tabs: tabs.map(t => ({ tabId: t.tabId, origin: new URL(t.url).origin, isActive: t.isActive })) }, null, 2)
      return { ok: true, text: `${json}\nCall preview_start or navigate with {"url": "https://…"} to open one.` }
    } else if (short === 'javascript_tool') {
      return { ok: true, text: JSON.stringify(tabs.find(t => t.tabId === input.tabId)?.url ?? '') }
    } else if (short === 'get_layout') {
      return { ok: true, text: JSON.stringify({ views: [{ panes: ['preview', 'terminal'] }] }) }
    } else if (short === 'list_terminal_tabs') {
      return { ok: true, text: JSON.stringify([{ tab_id: '1', title: 'dev', cwd: '/code/api' }]) }
    }
    return { ok: true, text: '{}' }
  }
  return { calls, tabs, call }
}

export function fakeHost(opts: { surface?: RenderSurface; server?: string; rrotor?: boolean; refuse?: string[] } = {}) {
  const tools = fakeTools(opts.refuse ?? [])
  const asked: string[] = []
  const server = fakeServer()
  const disk = fakeFiles()
  const time = fakeClock()
  const store = new Map<string, unknown>()
  const opened: string[] = []
  const copied: string[] = []
  const pane = async (_s: string, _t: string, args?: Record<string, unknown>): Promise<McpToolResult> => {
    opened.push(String(args?.url))
    return { content: [{ type: 'text', text: '{"tabId":"t1"}' }], isError: false } as McpToolResult
  }
  const gh: Host = {
    // rrotor's parts shown unless a test says shelved (GLYPHH_RROTOR, hooks/glyphh/shelved.ts).
    env: { home: async () => HOME, server: async () => opts.server, rrotor: async () => (opts.rrotor === false ? undefined : '1') },
    http: { fetch: (url, init) => server.fetch(url, init) },
    fs: disk.fs,
    process: { run: disk.run },
    clock: time.clock,
    store: { get: async k => store.get(k), set: async (k, v) => void store.set(k, v) },
    mcp: { call: pane },
    surface: async () => opts.surface ?? 'desktop',
    copy: async text => (copied.push(text), true),
    openPanel: async () => true,
    // As the engine: a prompt opening on a slash is refused (it would run as a command).
    ask: async text => {
      if (text.startsWith('/')) throw new Error('prompt.submit: a text beginning with / would run a command')
      asked.push(text)
    },
    tool: { call: tools.call },
    cwd: async () => '/code/web',
    openDip: async () => true,
    pluginRoot: '/mod',
    state: freshState(),
  }
  const note = async () => (await gh.state.note.get())?.text ?? ''
  return { gh, server, s: server.s, ...disk, store, opened, copied, advance: time.advance, note, tools, asked }
}
