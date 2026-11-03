// Glyphh's account, wired to the engine: the one file that holds `$` and the
// state atoms (the engine's scan reads them only here), handing the rest of
// hooks/glyphh a Host. Hooks: /glyphh, its panel and the session start
// (~/.glyphh); /dip, its pane and the active layout's brief.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, On, RenderSurface } from 'claude-code'

import type { AppsView, AuthState, DipView, GlyphhNote, GlyphhSection, Json } from '../../types'
import { FIRST_VIEW } from './apps'
import { glyphhCommand, startGlyphh } from './command'
import { brief, dipCommand, FIRST_DIP, loadDip, USAGE_DIP } from './dip'
import { DipPanel } from './dippanel'
import { rrotorShown } from './shelved'
import type { Host } from './host'
import { openUrl } from './open'
import { InlineSignIn } from './inline'
import { Panel } from './panel'
import { beginSignIn } from './sections/signin'
import { userOf } from './shape'
import type { Ui } from './ui'

const auth = atom({ plugin: 'glyphh', key: 'auth' } as const, { status: 'out' } as AuthState)
const section = atom({ plugin: 'glyphh', key: 'section' } as const, 'account' as GlyphhSection)
const me = atom({ plugin: 'glyphh', key: 'me' } as const, null as Json | null)
const lists = atom({ plugin: 'glyphh', key: 'lists' } as const, {} as Record<string, Json[]>)
const note = atom({ plugin: 'glyphh', key: 'note' } as const, null as GlyphhNote | null)
const inviteLink = atom({ plugin: 'glyphh', key: 'inviteLink' } as const, null as string | null)
const apps = atom({ plugin: 'glyphh', key: 'apps' } as const, FIRST_VIEW as AppsView)
const dipView = atom({ plugin: 'glyphh', key: 'dip' } as const, FIRST_DIP as DipView)

function hostState($: EngineInterface): Host['state'] {
  return {
    auth: { get: () => read($, auth), set: async fn => void (await update($, auth, fn)) },
    section: { get: () => read($, section), set: async fn => void (await update($, section, fn)) },
    me: { get: () => read($, me), set: async fn => void (await update($, me, fn)) },
    lists: { get: () => read($, lists), set: async fn => void (await update($, lists, fn)) },
    note: { get: () => read($, note), set: async fn => void (await update($, note, fn)) },
    inviteLink: { get: () => read($, inviteLink), set: async fn => void (await update($, inviteLink, fn)) },
    apps: { get: () => read($, apps), set: async fn => void (await update($, apps, fn)) },
    dip: { get: () => read($, dipView), set: async fn => void (await update($, dipView, fn)) },
  }
}

function host($: EngineInterface): Host {
  return {
    env: { home: () => $.env.get('HOME'), server: () => $.env.get('GLYPHH_SERVER_URL'), rrotor: () => $.env.get('GLYPHH_RROTOR') },
    http: { fetch: (url, init) => $.http.fetch(url, init) },
    fs: {
      read: async path => String(await $.fs.read(path)),
      readBytes: async path => (await $.fs.read(path, { as: 'bytes' })).base64,
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
    // environment means the desktop app.
    surface: async () => {
      const all = await $.session.surfaces().catch(() => [] as RenderSurface[])
      if (all.includes('desktop')) return 'desktop'
      if (all.length) return all[0] ?? null
      return (await $.env.get('TERM_PROGRAM').catch(() => 'x')) ? null : 'desktop'
    },
    copy: async (text, surface) => (await $.ui.copy({ text, surface })).isCopied,
    openPanel: async () => (await $.ui.open({ id: 'glyphh', title: 'Glyphh' })).isPlaced,
    // `void $.prompt.submit(...)`, not awaited: the prompt starts its own turn
    // once the session is idle.
    // Sent just after the hook that asks has finished: from inside a command.run
    // hook prompt.submit is refused (it would wait on the turn that hook holds).
    ask: async text => {
      $.clock.after(100, () => void $.prompt.submit({ text }).catch(async (err: unknown) => {
        const home = await $.env.get('HOME').catch(() => undefined)
        if (home) await $.fs.write(`${home}/.glyphh/ask-log.txt`, `${new Date().toISOString()} ${String(err).slice(0, 300)}\n`).catch(() => undefined)
      }))
    },
    // A tool the model could call, run by the mod through the permission check;
    // a refusal or an error is an answer too (the caller hands that step to Claude).
    tool: {
      call: async (tool, input) => {
        try {
          const r = (await $.tool.call({ tool, ...input } as never)) as { deny?: string; result?: unknown; text?: string; isError?: boolean }
          if (r.deny !== undefined) return { ok: false, text: r.deny }
          const text = typeof r.text === 'string' ? r.text : typeof r.result === 'string' ? r.result : JSON.stringify(r.result ?? '')
          return { ok: !r.isError, text }
        } catch (err) {
          return { ok: false, text: String(err).slice(0, 300) }
        }
      },
    },
    cwd: () => $.session.cwd(),
    openDip: async () => (await $.ui.open({ id: 'glyphh-dip', title: 'Dip' })).isPlaced,
    pluginRoot: $.plugin.root,
    state: hostState($),
  }
}

async function start($: EngineInterface) {
  await startGlyphh(host($))
  await loadDip(host($)).catch(() => undefined)
  await $.command
    .register({ name: 'dip', description: 'Dip: bounce to a workspace layout (folder, browser tabs, panes, terminals)', argumentHint: USAGE_DIP.replace('/dip ', '') })
    .catch(() => $.command.register({ name: 'glyphh-dip', description: 'Dip: bounce to a workspace layout' }))
  // rrotor shelved (2026-11-02, ./shelved): apps and publish only while it is shown.
  const shown = await rrotorShown(host($))
  const description = shown ? 'Glyphh: sign in, account, org, plan, billing, apps, publish' : 'Glyphh: sign in, account, org, plan, billing'
  const argumentHint = shown ? '[section | signin | signout | publish <file>]' : '[section | signin | signout]'
  await $.command
    .register({ name: 'glyphh', description, argumentHint })
    .catch(() => $.command.register({ name: 'glyphh-account', description }))
  // Claude's way in to the same sign-in: a tool of this mod's own; its result
  // draws the inline sign-in.
  await $.tool.register({
    name: 'glyphh_login',
    description:
      'Sign this device in to Glyphh: shows the sign-in inline in the chat (the code). Use when the user asks to sign in ' +
      'or log in to Glyphh. When it answers state "pending", open its url in the browser pane right away (Claude_Browser ' +
      'preview_start) and tell the user in one line to approve the code there. Says who is signed in already.',
    inputSchema: { type: 'object', properties: {} },
    isDeferred: false,
  })
}

export function registerGlyphh(on: On) {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await start($)
    return started
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
  on('command.run', { command: 'dip' }, ($, e) => dipCommand(host($), e.args))
  on('command.run', { command: 'glyphh-dip' }, ($, e) => dipCommand(host($), e.args))

  // The active layout's name, folder, tabs and brief, for Claude.
  on('prompt.compose', async ($, e, next) => {
    const composed = await next(e)
    const text = brief(await read($, dipView))
    return text ? { ...composed, sections: [...composed.sections, { id: 'glyphh:dip', text, scope: 'session' as const }] } : composed
  })

  on('ui.render', { component: 'Pane', requestId: 'glyphh-dip' }, async ($, e) => {
    if (e.surface === 'mobile') {
      const { Text } = $.ui.resolve(e as typeof e & { surface: 'mobile' })
      return <Text dimColor>Dip draws on the desktop or in a terminal.</Text>
    }
    const ui: Ui = $.ui.resolve(e as typeof e & { surface: 'desktop' })
    return DipPanel({ gh: host($), ui, surface: e.surface }, await read($, dipView))
  })
  on('command.run', { command: 'glyphh-account' }, ($, e) => glyphhCommand(host($), e.args))

  on('ui.render', { component: 'Pane', requestId: 'glyphh' }, async ($, e) => {
    if (e.surface === 'mobile') {
      const { Text } = $.ui.resolve(e as typeof e & { surface: 'mobile' })
      return <Text dimColor>Glyphh's panels draw on the desktop or in a terminal.</Text>
    }
    const ui: Ui = $.ui.resolve(e as typeof e & { surface: 'desktop' })
    const gh = host($)
    const ctx = { gh, ui, surface: e.surface, me: await read($, me), lists: await read($, lists), apps: await read($, apps), rrotor: await rrotorShown(gh) }
    return Panel(ctx, await read($, auth), await read($, section), await read($, note))
  })
}
