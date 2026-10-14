// Glyphh's account side of the mod, wired to the engine: the one file that
// holds `$` and the state atoms (the engine's scan reads them only here),
// handing the rest of hooks/glyphh a Host. Hooks: /glyphh, its panel, the
// session start (~/.glyphh), and dragged sizes on to the workspace files.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, On, RenderSurface } from 'claude-code'

import type { AuthState, GlyphhNote, GlyphhSection, Json, Layout, LicenseInfo } from '../../types'
import { DEFAULTS } from '../layouts'
import { glyphhCommand, startGlyphh } from './command'
import type { Host } from './host'
import { Panel } from './panel'
import type { Ui } from './ui'
import { saveSizes } from './wsfiles'

const auth = atom({ plugin: 'workspaces', key: 'auth' } as const, { status: 'out' } as AuthState)
const section = atom({ plugin: 'workspaces', key: 'section' } as const, 'account' as GlyphhSection)
const me = atom({ plugin: 'workspaces', key: 'me' } as const, null as Json | null)
const lists = atom({ plugin: 'workspaces', key: 'lists' } as const, {} as Record<string, Json[]>)
const note = atom({ plugin: 'workspaces', key: 'note' } as const, null as GlyphhNote | null)
const selected = atom({ plugin: 'workspaces', key: 'selected' } as const, null as string | null)
const inviteLink = atom({ plugin: 'workspaces', key: 'inviteLink' } as const, null as string | null)
const license = atom({ plugin: 'workspaces', key: 'license' } as const, null as LicenseInfo | null)
const layouts = atom({ plugin: 'workspaces', key: 'layouts' } as const, DEFAULTS as Layout[])
const active = atom({ plugin: 'workspaces', key: 'active' } as const, DEFAULTS[0]!.name)
const previous = atom({ plugin: 'workspaces', key: 'previous' } as const, null as string | null)

function hostState($: EngineInterface): Host['state'] {
  return {
    auth: { get: () => read($, auth), set: async fn => void (await update($, auth, fn)) },
    section: { get: () => read($, section), set: async fn => void (await update($, section, fn)) },
    me: { get: () => read($, me), set: async fn => void (await update($, me, fn)) },
    lists: { get: () => read($, lists), set: async fn => void (await update($, lists, fn)) },
    note: { get: () => read($, note), set: async fn => void (await update($, note, fn)) },
    selected: { get: () => read($, selected), set: async fn => void (await update($, selected, fn)) },
    inviteLink: { get: () => read($, inviteLink), set: async fn => void (await update($, inviteLink, fn)) },
    license: { get: () => read($, license), set: async fn => void (await update($, license, fn)) },
    layouts: { get: () => read($, layouts), set: async fn => void (await update($, layouts, fn)) },
    active: { get: () => read($, active), set: async fn => void (await update($, active, fn)) },
    previous: { get: () => read($, previous), set: async fn => void (await update($, previous, fn)) },
  }
}

function host($: EngineInterface): Host {
  return {
    env: { home: () => $.env.get('HOME'), server: () => $.env.get('GLYPHH_SERVER_URL') },
    http: { fetch: (url, init) => $.http.fetch(url, init) },
    fs: {
      read: async path => String(await $.fs.read(path)),
      write: (path, text) => $.fs.write(path, text),
      exists: path => $.fs.exists(path),
      list: path => $.fs.list(path),
    },
    process: { run: (argv, init) => $.process.run(argv, init) },
    clock: { now: () => $.clock.now(), after: (ms, fn) => $.clock.after(ms, fn) },
    store: { get: key => $.store.get(key), set: (key, value) => $.store.set(key, value as never) },
    mcp: { call: (server, tool, args) => $.mcp.call(server, tool, args) },
    // Which surfaces this session draws on (session.surface is deprecated): the
    // desktop app's first; with none attached yet, no terminal program in the
    // environment means the desktop app, as the grid's isDesktop does.
    surface: async () => {
      const all = await $.session.surfaces().catch(() => [] as RenderSurface[])
      if (all.includes('desktop')) return 'desktop'
      if (all.length) return all[0] ?? null
      return (await $.env.get('TERM_PROGRAM').catch(() => 'x')) ? null : 'desktop'
    },
    copy: async (text, surface) => (await $.ui.copy({ text, surface })).isCopied,
    openPanel: async () => (await $.ui.open({ id: 'glyphh', title: 'Glyphh' })).isPlaced,
    pluginRoot: $.plugin.root,
    state: hostState($),
  }
}

async function start($: EngineInterface) {
  await startGlyphh(host($))
  const description = 'Glyphh: sign in, account, org, plan, billing, workspaces'
  await $.command
    .register({ name: 'glyphh', description, argumentHint: '[section | signin | signout]' })
    .catch(() => $.command.register({ name: 'glyphh-account', description }))
}

export function registerGlyphh(on: On) {
  // After the grid's own session.start (which loads its saved sizes), so the
  // first run migrates them. Two matchers that together take every session:
  // the scan allows one unmatched session.start per plugin, the grid's.
  on('session.start', { isInteractive: true }, async ($, e, next) => {
    const started = await next(e)
    await start($)
    return started
  })
  on('session.start', { isInteractive: false }, async ($, e, next) => {
    const started = await next(e)
    await start($)
    return started
  })

  // The grid keeps dragged sizes in the store; they go on to the files.
  on('store.set', { key: 'layouts' }, async ($, e, next) => {
    const done = await next(e)
    if (Array.isArray(e.value)) await saveSizes(host($), e.value as Layout[]).catch(() => undefined)
    return done
  })

  on('command.run', { command: 'glyphh' }, ($, e) => glyphhCommand(host($), e.args))
  on('command.run', { command: 'glyphh-account' }, ($, e) => glyphhCommand(host($), e.args))

  on('ui.render', { component: 'Pane', requestId: 'glyphh' }, async ($, e) => {
    if (e.surface === 'mobile') {
      const { Text } = $.ui.resolve(e as typeof e & { surface: 'mobile' })
      return <Text dimColor>Glyphh's panels draw on the desktop or in a terminal.</Text>
    }
    const ui: Ui = $.ui.resolve(e as typeof e & { surface: 'desktop' })
    const gh = host($)
    const ctx = { gh, ui, surface: e.surface, me: await read($, me), lists: await read($, lists) }
    return Panel(ctx, await read($, auth), await read($, section), await read($, note))
  })
}
