// Games, wired to the engine: the one file of this module that holds
// `$` and the mod's state (the engine follows `$` and atoms only within the
// file whose hook received them), handing the rest closures. /games lists the
// games and starts one in the shared native overlay (../overlay), over
// Claude's window or the whole screen as the /config row `display` says; the
// overlay takes the pointer and keys while a game is on. Each game posts its
// score as it goes, and the top one is kept for the next round to beat.
// /games alone draws as the games card: each game with its icon, your best and
// Play, four to a page; until Games is bought, Play opens checkout instead.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, On, PluginOptions } from 'claude-code'

import { ancestorsOf, eventsOf, overlayHost, prepareOverlay, type OverlayDeps, type Placement, type Prepared } from '../overlay/host.ts'
import { selectTarget, type Target, type TerminalEnv } from '../overlay/target.ts'
import { INITIAL, refusal } from '../unlock/access.ts'
import { MOD, PRICE, PRODUCT } from '../unlock/config.ts'
import { buy, type Deps } from '../unlock/flow.ts'
import { verify } from '../unlock/verify.ts'
import { LOGO_ALT, LOGO_SVG } from '../unlock/logo.ts'
import { GAMES, gameDoc, gameOf } from './games/index.ts'
import type { Game } from './games/game.ts'
import { ICONS } from './icons.ts'
import { scoresOf, type Store } from './scores.ts'
import { settingsOf, type Settings } from './settings.ts'

const licence = atom({ plugin: 'games', key: 'licence' } as const, INITIAL)
/** The games card's page, from 0. */
const page = atom({ plugin: 'games', key: 'page' } as const, 0)

/** Games the card shows to a page. */
export const PAGE_SIZE = 4
/** How many pages the card has. */
export const PAGES = Math.ceil(GAMES.length / PAGE_SIZE)

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
  // Not the refusal line: that one draws as the unlock module's card, this as the games card.
  if (refusal(await read($, licence))) lines.push('', `${PRODUCT} is ${PRICE}, once: /games unlock buys it.`)
  return lines.join('\n')
}

/** Play on the card: the game, or checkout until Games is bought. */
async function press($: EngineInterface, game: Game): Promise<void> {
  if (refusal(await read($, licence))) return checkout($)
  const said = await play($, game).catch(err => `/games: ${short(err)}`)
  if (!said.startsWith(game.title)) $.ui.toast(said) // the overlay could not run
}

/** What /games unlock does, from the card's Play (a mod can't run its own
 *  command, and the engine follows $ only within this file). */
async function checkout($: EngineInterface): Promise<void> {
  const d: Deps = {
    store: { get: key => $.store.get(key), set: (key, value) => $.store.set(key, value), delete: key => $.store.delete(key) },
    state: { get: () => read($, licence), set: async fn => void (await update($, licence, fn)) },
    now: () => $.clock.now(),
    every: (ms, fn) => $.clock.every(ms, () => void fn()),
    check: async text => (await verify(text, MOD)) !== null,
    fetch: url => $.http.fetch(url),
    open: async url => (await $.process.run(['open', url]).catch(() => null))?.exitCode === 0,
    copy: async text => (await $.ui.copy({ text })).isCopied,
    toast: (text, ms) => $.ui.toast(text, ms ? { timeoutMs: ms } : undefined),
    log: text => $.ui.log(text),
  }
  await buy(d)
  if (!(await read($, licence)).licence) $.ui.toast(`Checkout for ${PRODUCT} (${PRICE}, once) is open in your browser. ${PRODUCT} unlocks on its own when you've paid.`)
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

  // /games alone (or /games list): the games card.
  on('ui.render', { component: 'CommandOutput' }, async ($, e, next) => {
    const args = e.props.args.trim().toLowerCase()
    if (e.props.command !== 'games' || e.props.isErrored || (args !== '' && args !== 'list')) return next(e)
    const { Box, Text, Button, ...els } = $.ui.resolve(e)
    // Every surface but the terminal draws SVG: the logo and the icons; the terminal gets words.
    const Svg = e.surface !== 'terminal' && 'Svg' in els ? els.Svg : null
    const at = Math.min(await read($, page), PAGES - 1)
    const scores = scoresOf(store($))
    const rows = []
    for (const game of GAMES.slice(at * PAGE_SIZE, (at + 1) * PAGE_SIZE)) {
      const best = await scores.best(game.name)
      rows.push(
        <Box key={game.name} flexDirection="row" alignItems="center" gap={2}>
          {Svg && ICONS[game.name] ? <Svg source={ICONS[game.name]!} alt="" width={18} height={18} /> : null}
          <Box flexGrow={1}>
            <Text>{game.title}</Text>
          </Box>
          <Text dimColor>{best > 0 ? best.toLocaleString('en-GB') : ''}</Text>
          <Button key={`play:${game.name}`} label="Play" variant="secondary" onPress={() => void press($, game)} />
        </Box>,
      )
    }
    const turn = (by: number) => () => void update($, page, p => Math.max(0, Math.min(PAGES - 1, Math.min(p, PAGES - 1) + by)))
    return (
      <Box flexDirection="column" gap={1} paddingX={2} paddingY={1} borderStyle="round" borderDimColor>
        <Box flexDirection="row" alignItems="center" gap={1}>
          {Svg ? <Svg source={LOGO_SVG} alt={LOGO_ALT} height={16} /> : <Text bold>glyphh</Text>}
          <Text dimColor>Games</Text>
        </Box>
        {rows}
        {PAGES > 1 ? (
          <Box flexDirection="row" justifyContent="flex-end" alignItems="center" gap={1}>
            <Button key="prev" label="‹" plain dimColor={at === 0} onPress={turn(-1)} />
            <Text dimColor>
              {at + 1} of {PAGES}
            </Text>
            <Button key="next" label="›" plain dimColor={at === PAGES - 1} onPress={turn(1)} />
          </Box>
        ) : null}
      </Box>
    )
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
