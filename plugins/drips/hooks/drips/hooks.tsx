// Drips, wired to the engine: the one file of this module that holds `$` and
// the mod's state (the engine follows `$` and atoms only within the file
// whose hook received them), handing the rest closures. It runs the Drips
// page's helper (helper/server.mjs), detached so it outlives the mod's
// reloads, and the fullscreen overlay (native/overlay.swift), one process per
// effect. Where effects play is the /config row `display`.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, On, PluginOptions, Timer } from 'claude-code'

import type { HelperInfo } from '../../types'
import { INITIAL, refusal } from '../licence/access.ts'
import { BUILTIN_EFFECT_LIST, BUILTIN_EFFECTS } from './effects.ts'
import { createFun } from './fun.ts'
import { eventsOf, fullscreenHost, prepareOverlay, type FullscreenDeps, type Prepared } from './fullscreen.ts'
import { deleteCustom, dripId, listCustoms, readCustoms, saveCustom, type Store } from './library.ts'
import { HELPER_FILES, linkTo, versionOf, type Link, type PageMessage } from './link.ts'
import { createManager, customEffects, type Host, type Manager } from './manager.ts'
import { findNode, NODE_MISSING } from './node.ts'
import { settingsOf, type Settings } from './settings.ts'
import { showPage, shownText, windowHost, type PageDeps, type WindowHost } from './window.ts'

const licence = atom({ plugin: 'drips', key: 'licence' } as const, INITIAL)
const helperInfo = atom({ plugin: 'drips', key: 'helper' } as const, null as HelperInfo | null)
const pageTab = atom({ plugin: 'drips', key: 'pageTab' } as const, null as string | null)
const nodePath = atom({ plugin: 'drips', key: 'node' } as const, null as string | null)

const TOOL_PREFIX = 'mcp__drips__'
const NOT_A_RECIPE = ['save', 'delete', 'list']

/** This load's pieces: made at the session's start (a reload makes them again). */
type Mod = { manager: Manager; window: WindowHost; fullscreen: Promise<Prepared> | null; fun: ReturnType<typeof createFun> }
let settings: Settings
let mod: Mod | null = null
/** The helper this load talks to, and the timer that collects the page's messages. */
let helper: Link | null = null
let collecting: Timer | null = null
let starting: Promise<Link> | null = null
/** The fullscreen fallback is said once per load. */
let isFallbackSaid = false

const short = (err: unknown) => String(err instanceof Error ? err.message : err).replace(/^(Hooks)?Error: /, '').slice(0, 300)

function store($: EngineInterface): Store {
  return { get: key => $.store.get(key), set: (key, value) => $.store.set(key, value) }
}

function pageDeps($: EngineInterface): PageDeps {
  return {
    isDesktop: async () => (await $.session.surfaces()).includes('desktop'),
    mcp: (server, tool, args) => $.mcp.call(server, tool, args),
    openExternal: async url => (await $.process.run(['open', url]).catch(() => null))?.exitCode === 0,
    // A prompt submitted from inside a command would wait on the command
    // itself: it goes once the command has returned.
    ask: text =>
      void $.clock.after(0, () => {
        $.prompt.submit({ text }).catch(() => $.ui.toast('The Browser pane is not available: allow mcp__Claude_Browser__preview_start'))
      }),
    sleep: ms => $.clock.sleep(ms),
    link: () => startHelper($),
    tab: { get: () => read($, pageTab), set: async fn => void (await update($, pageTab, fn)) },
  }
}

function fullscreenDeps($: EngineInterface): FullscreenDeps {
  return {
    run: (argv, timeoutMs) => $.process.run(argv, timeoutMs ? { timeoutMs } : undefined).catch(() => null),
    spawn: (argv, input) => eventsOf($.process.spawn({ argv, input })),
    read: async path => String(await $.fs.read(path)),
    exists: path => $.fs.exists(path),
    home: () => $.env.get('HOME'),
    root: $.plugin.root,
  }
}

function build($: EngineInterface): Mod {
  const report = (err: unknown) => $.ui.toast(`Drips: ${short(err)}`)
  const manager = createManager({
    store: store($),
    customs: () => readCustoms(store($)),
    after: (ms, fn) => void $.clock.after(ms, fn),
    report,
  })
  const m: Mod = { manager, window: windowHost(pageDeps($)), fullscreen: null, fun: null as never }
  m.fun = createFun(
    {
      isAllowed: async () => !(await refused($)),
      play: async recipe => void (await manager.execute(() => hostOf($, m), recipe)),
      ensure: async effect => manager.ensure(await hostOf($, m), effect),
      release: effect => manager.release(effect),
      after: (ms, fn) => $.clock.after(ms, fn),
      report,
    },
    settings,
  )
  return m
}

const modOf = ($: EngineInterface) => (mod ??= build($))

/** Where effects play now: the setting's host; Claude's window for a preview,
 *  and where the fullscreen overlay cannot run here (said once). */
async function hostOf($: EngineInterface, m: Mod, preview = false): Promise<Host> {
  if (!preview && settings.display === 'fullscreen') {
    m.fullscreen ??= prepareOverlay(fullscreenDeps($))
    const prepared = await m.fullscreen
    if ('binary' in prepared) return fullscreenHost(fullscreenDeps($), prepared.binary)
    if (!isFallbackSaid) $.ui.toast(`${prepared.missing} Playing in Claude's window instead.`)
    isFallbackSaid = true
  }
  if (!(await read($, nodePath))) throw new Error(NODE_MISSING)
  return m.window
}

/** Why effects may not play now (the trial is over), or null. */
async function refused($: EngineInterface): Promise<string | null> {
  return refusal(await read($, licence), await $.clock.now())
}

// ── The Drips page's helper ─────────────────────────────────────────────────

const linkOf = ($: EngineInterface, info: HelperInfo) => linkTo((url, init) => $.http.fetch(url, init), info.port, info.token)

async function helperVersion($: EngineInterface): Promise<string> {
  const texts = []
  for (const f of HELPER_FILES) texts.push(String(await $.fs.read(`${$.plugin.root}/helper/${f}`).catch(() => '')))
  return versionOf(texts)
}

/** The page's saved recipes and effects, sent to the helper. */
async function pushLibrary($: EngineInterface): Promise<void> {
  await helper?.library({ drips: await listCustoms(store($)), effects: BUILTIN_EFFECTS, display: settings.display })
}

/** What the page asked: a preview played, everything stopped, a recipe saved or deleted. */
async function onPage($: EngineInterface, m: PageMessage): Promise<void> {
  const { manager, window } = modOf($)
  if (m.t === 'closed') return window.closed(m.effect)
  if (m.t === 'stop') {
    await manager.stopAll()
    await helper?.stop()
    return
  }
  if (m.t === 'play') {
    const no = await refused($)
    if (no) return $.ui.toast(no)
    await manager.execute(() => hostOf($, modOf($), true), m.recipe, { preview: true })
    return
  }
  if (m.t === 'save') {
    if (!dripId(m.name) || customEffects(m.recipe).length === 0) return $.ui.toast('Drips: a drip needs a name and at least one effect.')
    if (m.original && dripId(m.original) !== dripId(m.name)) await deleteCustom(store($), m.original)
    await saveCustom(store($), m.name, m.recipe)
  } else await deleteCustom(store($), m.name)
  await pushLibrary($)
}

/** Talks to a running helper: the page's messages collected every second,
 *  which keeps it alive; one that stopped answering is let go. */
async function attach($: EngineInterface, link: Link): Promise<Link> {
  helper = link
  collecting?.cancel()
  collecting = $.clock.every(1000, () => {
    link
      .inbox()
      .then(async messages => {
        for (const m of messages) await onPage($, m).catch(err => $.ui.toast(`Drips: ${short(err)}`))
      })
      .catch(async () => {
        if (helper !== link) return
        collecting?.cancel()
        helper = null
        await update($, helperInfo, () => null)
      })
  })
  await pushLibrary($)
  return link
}

/** The helper kept from before this load: found again when its code is this
 *  copy's (its looping effects ended: this load starts with none); told to
 *  leave when it is not. */
async function reattach($: EngineInterface, version: string): Promise<Link | null> {
  const kept = await read($, helperInfo)
  if (!kept) return null
  const link = linkOf($, kept)
  const running = await link.state().then(s => s.version, () => null)
  if (running === version) {
    await link.stop().catch(() => undefined)
    return attach($, link)
  }
  if (running !== null) await link.quit().catch(() => undefined)
  collecting?.cancel()
  helper = null
  await update($, helperInfo, () => null)
  return null
}

const randomHex = (n: number) => Array.from(crypto.getRandomValues(new Uint8Array(n)), b => b.toString(16).padStart(2, '0')).join('')

/** The page's helper: the one running, or a new one started detached on a
 *  port and with a token chosen here; up when it answers. */
function startHelper($: EngineInterface): Promise<Link> {
  if (helper) return Promise.resolve(helper)
  starting ??= (async () => {
    const version = await helperVersion($)
    const kept = await reattach($, version)
    if (kept) return kept
    const node = await read($, nodePath)
    if (!node) throw new Error(NODE_MISSING)
    for (let attempt = 0; attempt < 2; attempt++) {
      const info: HelperInfo = { port: 20000 + (crypto.getRandomValues(new Uint16Array(1))[0]! % 40000), token: randomHex(24) }
      const launch = $.process.spawn({
        argv: [node, `${$.plugin.root}/helper/server.mjs`],
        env: { DRIPS_DETACH: '1', DRIPS_PORT: String(info.port), DRIPS_TOKEN: info.token, DRIPS_VERSION: version },
      })
      for await (const _ of launch); // the launcher starts the helper in its own session and exits
      const link = linkOf($, info)
      for (let i = 0; i < 20; i++) {
        if ((await link.state().then(s => s.version, () => null)) === version) {
          await update($, helperInfo, () => info)
          return attach($, link)
        }
        await $.clock.sleep(100)
      }
    }
    throw new Error('the Drips page did not start')
  })().finally(() => {
    starting = null
  })
  return starting
}

// ── Hooks ───────────────────────────────────────────────────────────────────

async function registerAll($: EngineInterface): Promise<void> {
  await $.command.register({
    name: 'drip',
    description: 'Play a visual effect: /drip confetti, /drip 3 hearts stars, /drip -1 aurora; list, save <name> <recipe>, delete <name>, stop',
    argumentHint: '<recipe> | list | save <name> <recipe> | delete <name> | stop',
    immediate: true,
  })
  await $.command.register({ name: 'drips', description: 'Open the Drips page: your saved drips, and an editor; key <licence> unlocks Drips', argumentHint: '[key <licence>]' })
  await $.tool.register({
    name: 'play_drip',
    description:
      'Play a visual effect over Claude for the person: a recipe such as "confetti", "3 hearts stars", "0.6 fireworks", ' +
      '"-1 aurora" (persistent: plays until fired again or "stop"), a saved drip\'s name, or "stop". list_drips lists the effects.',
    inputSchema: { type: 'object', properties: { recipe: { type: 'string', description: 'The drip recipe' } }, required: ['recipe'] },
    isDeferred: false,
  })
  await $.tool.register({
    name: 'list_drips',
    description: "List the visual effects play_drip can play, and the person's saved drips.",
    inputSchema: { type: 'object', properties: {} },
    isDeferred: false,
  })
}

export function drips(on: On, options: PluginOptions) {
  settings = settingsOf(options)
  mod = null
  helper = null
  isFallbackSaid = false

  on('session.start', async ($, e, next) => {
    mod = build($)
    await update($, nodePath, () => null)
    const node = await findNode({ run: argv => $.process.run(argv).catch(() => null) })
    await update($, nodePath, () => node)
    await reattach($, await helperVersion($)).catch(() => null) // a reload keeps the page up
    await registerAll($)
    return next(e)
  })

  on('command.run', { command: 'drip' }, async ($, e) => {
    const line = e.args.trim()
    const sub = line.split(/\s+/)[0]?.toLowerCase() ?? ''
    if (!['list', 'save', 'delete', 'stop'].includes(sub)) {
      const no = await refused($)
      if (no) return { text: no }
    }
    try {
      const m = modOf($)
      const text = await m.manager.execute(() => hostOf($, m), line)
      if (sub === 'save' || sub === 'delete') await pushLibrary($).catch(() => undefined)
      if (sub === 'stop') await helper?.stop().catch(() => undefined) // frames a reload left behind
      return { text }
    } catch (err) {
      return { text: `/drip: ${short(err)}` }
    }
  })

  on('command.run', { command: 'drips' }, async ($, e) => {
    if (e.args.trim()) return { text: 'Usage: /drips [key <licence>]' }
    if (!(await read($, nodePath))) return { text: NODE_MISSING }
    try {
      return { text: shownText(await showPage(pageDeps($))) }
    } catch (err) {
      return { text: `Drips page ✗ ${short(err)}` }
    }
  })

  on('tool.call', { tool: 'mcp__drips__play_drip' }, async ($, e) => {
    const no = await refused($)
    if (no) return { result: { error: no } }
    const recipe = String((e.input as { recipe?: unknown } | undefined)?.recipe ?? '').trim()
    if (NOT_A_RECIPE.includes(recipe.split(/\s+/)[0]?.toLowerCase() ?? '')) return { result: { error: 'play_drip takes a recipe or "stop"; list_drips lists the effects.' } }
    try {
      const m = modOf($)
      return { result: { status: await m.manager.execute(() => hostOf($, m), recipe) } }
    } catch (err) {
      return { result: { error: short(err) } }
    }
  })

  on('tool.call', { tool: 'mcp__drips__list_drips' }, async ($, e) => {
    const no = await refused($)
    if (no) return { result: { error: no } }
    return { result: { effects: BUILTIN_EFFECT_LIST, custom: await listCustoms(store($)), running: modOf($).manager.running() } }
  })

  // The fun hooks: each does nothing unless its /config toggle is on.
  on('tool.call', async ($, e, next) => {
    if (!settings.matrixWhileTools || e.agentId || String(e.tool).startsWith(TOOL_PREFIX)) return next(e)
    const { fun } = modOf($)
    void fun.toolStart()
    try {
      return await next(e)
    } finally {
      fun.toolEnd()
    }
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    void modOf($)
      .fun.turnEnd({ durationMs: e.durationMs, reason: e.reason, isMainLoop: !e.agentId })
      .catch(err => $.ui.toast(`Drips: ${short(err)}`))
    return next(e)
  })
}
