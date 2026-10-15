// Effects over the whole screen: the native overlay (native/overlay.swift),
// compiled with swiftc the first time it is needed and kept in
// ~/Library/Caches/glyphh-drips, one binary per version of its source. Each
// effect is one overlay process; a persistent one is ended with SIGTERM.
// Works on FullscreenDeps, closures over `$` that ./hooks.tsx hands it.
import { loopDoc, oneShotDoc, type Doc } from './docs.ts'
import type { Closer, Host } from './manager.ts'
import { binaryPath, compileArgv, digestOf, lineSplitter, parseEvent, parseScreen, playRequest, type OverlayEvent, type Screen } from './overlay.ts'

export type RunResult = { exitCode: number; stdout: string; stderr: string }

export type FullscreenDeps = {
  /** A command's result, or null when it could not start. */
  run(argv: readonly string[], timeoutMs?: number): Promise<RunResult | null>
  /** Starts `argv` with `input` on stdin: the overlay's events, in order, until it exits. */
  spawn(argv: readonly string[], input: string): AsyncIterable<OverlayEvent>
  read(path: string): Promise<string>
  exists(path: string): Promise<boolean>
  home(): Promise<string | undefined>
  /** The mod's folder. */
  root: string
}

export const SWIFT_MISSING = 'Fullscreen effects need Swift: install the Xcode Command Line Tools (xcode-select --install).'
export const MAC_ONLY = 'Fullscreen effects need macOS.'
const BUILD_MS = 5 * 60_000

export type Prepared = { binary: string } | { missing: string }

const firstLine = (text: string) => text.trim().split('\n')[0]?.slice(0, 160) ?? ''

/** The overlay's events from a spawned child's output pieces. */
export async function* eventsOf(chunks: AsyncIterable<{ stream: string; text: string }>): AsyncGenerator<OverlayEvent> {
  const split = lineSplitter()
  for await (const chunk of chunks) {
    if (chunk.stream !== 'stdout') continue
    for (const line of split(chunk.text)) {
      const ev = parseEvent(line)
      if (ev) yield ev
    }
  }
}

/** The overlay binary for this copy of the mod: the one built before, or built now. */
export async function prepareOverlay(d: FullscreenDeps): Promise<Prepared> {
  if ((await d.run(['uname', '-s']))?.stdout.trim() !== 'Darwin') return { missing: MAC_ONLY }
  const home = await d.home()
  if (!home) return { missing: 'Fullscreen effects need HOME to be set.' }
  const source = `${d.root}/native/overlay.swift`
  const binary = binaryPath(home, await digestOf(await d.read(source)))
  if (await d.exists(binary)) return { binary }
  if ((await d.run(['xcode-select', '-p']))?.exitCode !== 0) return { missing: SWIFT_MISSING }
  const found = await d.run(['xcrun', '--find', 'swiftc'])
  const swiftc = found?.exitCode === 0 ? found.stdout.trim() : ''
  if (!swiftc) return { missing: SWIFT_MISSING }
  await d.run(['/bin/mkdir', '-p', binary.slice(0, binary.lastIndexOf('/'))])
  const building = `${binary}.building`
  const built = await d.run(compileArgv(swiftc, source, building), BUILD_MS)
  if (built?.exitCode !== 0) return { missing: `The fullscreen overlay did not build: ${firstLine(built?.stderr ?? 'swiftc did not run')}` }
  const moved = await d.run(['/bin/mv', '-f', building, binary])
  if (moved?.exitCode !== 0) return { missing: `The fullscreen overlay could not be kept: ${firstLine(moved?.stderr ?? '')}` }
  return { binary }
}

type Shown = { pid: number; closed: Promise<void> }

export function fullscreenHost(d: FullscreenDeps, binary: string): Host {
  async function screen(): Promise<Screen> {
    const r = await d.run([binary, 'screen'], 10_000)
    const s = r?.exitCode === 0 ? parseScreen(r.stdout) : null
    if (!s) throw new Error('The fullscreen overlay could not find the screen.')
    return s
  }

  /** Opens one overlay; resolves once it is on screen. */
  async function show(doc: Doc, s: Screen): Promise<Shown> {
    const events = d.spawn([binary, 'play'], playRequest(doc.html, s, doc.closeAfterMs))[Symbol.asyncIterator]()
    const first = await events.next()
    if (first.done || first.value.t !== 'shown') {
      const said = !first.done && first.value.t === 'error' ? `: ${first.value.message}` : ''
      throw new Error(`The fullscreen overlay did not open${said}`)
    }
    const closed = (async () => {
      while (!(await events.next()).done); // read to the end: the child has exited
    })()
    return { pid: first.value.pid, closed }
  }

  return {
    async oneShot(effect, opacity) {
      const s = await screen()
      const shown = await show(oneShotDoc(effect, s.w, s.h, opacity), s)
      void shown.closed.catch(() => undefined)
    },
    async persistent(effect, opacity, maxMs, onClosed): Promise<Closer> {
      const s = await screen()
      const shown = await show(loopDoc(effect, s.w, s.h, opacity, maxMs), s)
      let isClosed = false
      const ended = () => {
        isClosed = true
        onClosed()
      }
      void shown.closed.then(ended, ended)
      return {
        close: async () => {
          if (!isClosed) await d.run(['/bin/kill', '-TERM', String(shown.pid)])
        },
      }
    },
  }
}
