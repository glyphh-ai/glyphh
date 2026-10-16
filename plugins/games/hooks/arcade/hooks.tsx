// Games, wired to the engine: the one file of this module that holds
// `$` and the mod's state (the engine follows `$` and atoms only within the
// file whose hook received them), handing the rest closures. /games lists the
// games and starts one in the shared native overlay (../overlay), over
// Claude's window or the whole screen as the /config row `display` says; the
// overlay takes the pointer and keys while a game is on. Each game posts its
// score as it goes, and the top one is kept for the next round to beat.
import { atom, read } from 'claude-code'
import type { EngineInterface, On, PluginOptions } from 'claude-code'

import { ancestorsOf, eventsOf, overlayHost, prepareOverlay, type OverlayDeps, type Placement, type Prepared } from '../overlay/host.ts'
import { selectTarget, type Target, type TerminalEnv } from '../overlay/target.ts'
import { INITIAL, refusal } from '../unlock/access.ts'
import { GAMES, gameDoc, gameOf } from './games/index.ts'
import type { Game } from './games/game.ts'
import { scoresOf, type Store } from './scores.ts'
import { settingsOf, type Settings } from './settings.ts'

const licence = atom({ plugin: 'games', key: 'licence' } as const, INITIAL)

let settings: Settings
/** This load's pieces: the overlay's binary, built on first use, and the window Claude runs in. */
let native: Promise<Prepared> | null = null
let target: Promise<Target | null> | null = null
/** Said once per load: Claude's window not found. */
let isMissedSaid = false

const short = (err: unknown) => String(err instanceof Error ? err.message : err).replace(/^(Hooks)?Error: /, '').slice(0, 300)

function store($: EngineInterface): Store {
  return { get: key => $.store.get(key), set: (key, value) => $.store.set(key, value) }
}

function overlayDeps($: EngineInterface): OverlayDeps {
  return {
    run: (argv, opts) => $.process.run(argv, opts).catch(() => null),
    spawn: (argv, input) => eventsOf($.process.spawn({ argv, input })),
    read: async path => String(await $.fs.read(path)),
    exists: path => $.fs.exists(path),
    home: () => $.env.get('HOME'),
    root: $.plugin.root,
  }
}

/** The window Claude runs in: the desktop app's, or the terminal's that hosts this session. */
async function findTarget($: EngineInterface, binary: string): Promise<Target | null> {
  const env: TerminalEnv = {
    TERM_PROGRAM: await $.env.get('TERM_PROGRAM'),
    __CFBundleIdentifier: await $.env.get('__CFBundleIdentifier'),
    TERM: await $.env.get('TERM'),
  }
  const isDesktop = (await $.session.surfaces()).includes('desktop')
  return selectTarget({ isDesktop, env, ancestors: await ancestorsOf(overlayDeps($), binary) })
}

function placement($: EngineInterface, binary: string): Placement {
  if (settings.display === 'fullscreen') return { kind: 'fullscreen' }
  return {
    kind: 'window',
    target: () => (target ??= findTarget($, binary)),
    missed: () => {
      if (!isMissedSaid) $.ui.toast("Games could not find Claude's window: games play over the screen under the pointer.")
      isMissedSaid = true
    },
  }
}

/** The list /games answers with: each game, its other names and your best. */
async function listing($: EngineInterface): Promise<string> {
  const scores = scoresOf(store($))
  const lines = ['Games. /games <name> starts one:']
  for (const g of GAMES) {
    const best = await scores.best(g.name)
    lines.push(`  ${g.name.padEnd(9)} ${g.title}${best > 0 ? `  ·  best ${best}` : ''}`)
  }
  const no = refusal(await read($, licence))
  if (no) lines.push('', no)
  return lines.join('\n')
}

/** Starts `game` in the overlay; resolves once it is on screen. The score it
 *  posts is kept when it beats the top one. */
async function play($: EngineInterface, game: Game): Promise<string> {
  native ??= prepareOverlay(overlayDeps($))
  const prepared = await native
  if (!('binary' in prepared)) return prepared.missing
  const scores = scoresOf(store($))
  const best = await scores.best(game.name)
  const { show } = overlayHost(overlayDeps($), prepared.binary, placement($, prepared.binary))
  const shown = await show(
    s => gameDoc(game, s.w, s.h, best, settings.sounds),
    async ev => void (ev.t === 'score' && (await scores.keep(game.name, ev.score))),
  )
  void shown.closed.catch(() => undefined)
  return `${game.title}${best > 0 ? `: your best is ${best}` : ''}. Esc quits, M mutes.`
}

export function arcade(on: On, options: PluginOptions) {
  settings = settingsOf(options)
  native = null
  target = null
  isMissedSaid = false

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'games',
      description: 'Games: /games lists the games; /games blocks starts one; unlock buys Games ($8, once); key <licence> unlocks it with a licence from another machine',
      argumentHint: '[<game> | unlock | key <licence>]',
      immediate: true,
    })
    return next(e)
  })

  on('command.run', { command: 'games' }, async ($, e) => {
    const name = e.args.trim()
    // As /drips: `list` (or nothing) lists, anything else is a name to play.
    if (!name || name.toLowerCase() === 'list') return { text: await listing($) }
    const game = gameOf(name)
    if (!game) return { text: `No game called "${name}". /games list lists them.` }
    const no = refusal(await read($, licence))
    if (no) return { text: no }
    try {
      return { text: await play($, game) }
    } catch (err) {
      return { text: `/games: ${short(err)}` }
    }
  })
}
