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
  license: value(null),
})

export function fakeHost(opts: { surface?: RenderSurface; server?: string } = {}) {
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
    env: { home: async () => HOME, server: async () => opts.server },
    http: { fetch: (url, init) => server.fetch(url, init) },
    fs: disk.fs,
    process: { run: disk.run },
    clock: time.clock,
    store: { get: async k => store.get(k), set: async (k, v) => void store.set(k, v) },
    mcp: { call: pane },
    surface: async () => opts.surface ?? 'desktop',
    copy: async text => (copied.push(text), true),
    openPanel: async () => true,
    ask: async () => undefined,
    pluginRoot: '/mod',
    state: freshState(),
  }
  const note = async () => (await gh.state.note.get())?.text ?? ''
  return { gh, server, s: server.s, ...disk, store, opened, copied, advance: time.advance, note }
}
