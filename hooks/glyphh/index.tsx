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
import { openUrl } from './open'
import { InlineSignIn } from './inline'
import { Panel } from './panel'
import { beginSignIn } from './sections/signin'
import { userOf } from './shape'
import type { Ui } from './ui'
import { saveSizes } from './wsfiles'

const auth = atom({ plugin: 'glyphh', key: 'auth' } as const, { status: 'out' } as AuthState)
const section = atom({ plugin: 'glyphh', key: 'section' } as const, 'account' as GlyphhSection)
const me = atom({ plugin: 'glyphh', key: 'me' } as const, null as Json | null)
const lists = atom({ plugin: 'glyphh', key: 'lists' } as const, {} as Record<string, Json[]>)
const note = atom({ plugin: 'glyphh', key: 'note' } as const, null as GlyphhNote | null)
const selected = atom({ plugin: 'glyphh', key: 'selected' } as const, null as string | null)
const inviteLink = atom({ plugin: 'glyphh', key: 'inviteLink' } as const, null as string | null)
const license = atom({ plugin: 'glyphh', key: 'license' } as const, null as LicenseInfo | null)
const layouts = atom({ plugin: 'glyphh', key: 'layouts' } as const, DEFAULTS as Layout[])
const active = atom({ plugin: 'glyphh', key: 'active' } as const, DEFAULTS[0]!.name)
const previous = atom({ plugin: 'glyphh', key: 'previous' } as const, null as string | null)

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
    // As the grid's layoutToPane: `void $.prompt.submit(...)`, not awaited; the
    // prompt starts its own turn once the session is idle.
    // Sent just after the hook that asks has finished: from inside a command.run
    // hook prompt.submit is refused (it would wait on the turn that hook holds).
    ask: async text => {
      $.clock.after(100, () => void $.prompt.submit({ text }).catch(async (err: unknown) => {
        const home = await $.env.get('HOME').catch(() => undefined)
        if (home) await $.fs.write(`${home}/.glyphh/ask-log.txt`, `${new Date().toISOString()} ${String(err).slice(0, 300)}\n`).catch(() => undefined)
      }))
    },
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
  // Claude's way in to the same sign-in: a tool of this mod's own, as the grid
  // registers page_read; its result draws the inline sign-in.
  await $.tool.register({
    name: 'glyphh_login',
    description:
      'Sign this machine in to Glyphh: shows the sign-in inline in the chat (the code). Use when the user asks to sign in ' +
      'or log in to Glyphh. When it answers state "pending", open its url in the browser pane right away (Claude_Browser ' +
      'preview_start) and tell the user in one line to approve the code there. Says who is signed in already.',
    inputSchema: { type: 'object', properties: {} },
    isDeferred: false,
  })
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

  // Asking Claude to sign in (the card's tool, from this mod's server or a
  // Glyphh connector) opens the approval page in the browser pane right then:
  // inside the person's own request, which auto mode accepts, unlike an open
  // from a timer later.
  on('tool.call', async ($, e, next) => {
    const r = await next(e)
    if (typeof e.tool === 'string' && e.tool.endsWith('__glyphh_sign_in')) {
      const url = JSON.stringify(r).match(/https?:\/\/[^"\s\\]+\/v1\/device\?code=[A-Z0-9-]+/)?.[0]
      if (url) await openUrl(host($), url).catch(() => false)
    }
    return r
  })
  // glyphh_login: start the sign-in (the login page opens in the browser pane,
  // inside the person's request, which auto mode accepts) and answer its state.
  on('tool.call', { tool: 'mcp__glyphh__glyphh_login' }, async $ => {
    const gh = host($)
    if ((await read($, auth)).status !== 'in') await beginSignIn(gh)
    const a = await read($, auth)
    const m = await read($, me)
    if (a.status === 'in') return { result: JSON.stringify({ state: 'signed_in', email: m ? userOf(m).email : undefined }) }
    if (a.status === 'pending') return { result: JSON.stringify({ state: 'pending', user_code: a.user_code, url: a.verification_uri_complete }) }
    return { result: JSON.stringify({ state: 'signed_out', error: a.error }) }
  })
  // The inline sign-in, in place of the tool's result row and of
  // /glyphh login's reply row.
  on('ui.render', { component: 'ToolResult' }, async ($, e, next) => {
    if (e.props.tool !== 'mcp__glyphh__glyphh_login' || e.surface === 'mobile') return next(e)
    const ui: Ui = $.ui.resolve(e as typeof e & { surface: 'desktop' })
    return InlineSignIn(ui, await read($, auth), await read($, me))
  })
  on('ui.render', { component: 'CommandOutput' }, async ($, e, next) => {
    const login = ['login', 'signin', 'sign-in'].includes(e.props.args.trim().toLowerCase())
    if (e.props.command !== 'glyphh' || !login || e.surface === 'mobile') return next(e)
    const ui: Ui = $.ui.resolve(e as typeof e & { surface: 'desktop' })
    return InlineSignIn(ui, await read($, auth), await read($, me))
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
