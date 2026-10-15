// runner.mjs — effects over the Drips page: the Glyphh app's web runner
// (web/src/drip-web-runner.js at v2.0.2). Each effect's document plays in a
// full-viewport, pointer-events:none, sandboxed (allow-scripts) <iframe
// srcdoc> at a very high z-index. A one-shot frame goes when its document
// posts "__drip_close__" or its time is up; a looping frame stays until the
// mod closes it, Esc or Stop clears it, or its time is up (then the mod is
// told). The mod decides what plays and when (staggering, toggling); this
// only shows it. DOM-free at its top level: createRunner takes the page's
// means, so the mod's tests drive it with fakes.

export const DRIP_Z = 2147483000
export const CLOSE_SIGNAL = "__drip_close__"

/** A frame in the page, made from an effect's document. */
export function makeFrame(doc, html) {
  const f = doc.createElement("iframe")
  f.setAttribute("sandbox", "allow-scripts")
  f.setAttribute("aria-hidden", "true")
  f.style.cssText = `position:fixed;inset:0;width:100%;height:100%;border:0;background:transparent;pointer-events:none;z-index:${DRIP_Z};color-scheme:normal;`
  f.srcdoc = html
  doc.body.appendChild(f)
  return f
}

/**
 * @param {{ frame(html: string): { contentWindow: unknown, remove(): void },
 *           later(ms: number, fn: () => void): unknown, cancel(timer: unknown): void,
 *           loopClosed(effect: string): void }} means
 */
export function createRunner(means) {
  const loops = new Map() // effect → { frame, timer }
  const byWindow = new Map() // a frame's window → its teardown

  function track(frame, teardown) {
    if (frame.contentWindow) byWindow.set(frame.contentWindow, teardown)
  }
  function untrack(frame) {
    if (frame.contentWindow) byWindow.delete(frame.contentWindow)
  }

  function oneShot(html, closeAfterMs) {
    const frame = means.frame(html)
    let done = false
    let timer = null
    const teardown = () => {
      if (done) return
      done = true
      means.cancel(timer)
      untrack(frame)
      frame.remove()
    }
    track(frame, teardown)
    timer = means.later(closeAfterMs, teardown)
  }

  function endLoop(effect, tellMod) {
    const loop = loops.get(effect)
    if (!loop) return
    loops.delete(effect)
    means.cancel(loop.timer)
    untrack(loop.frame)
    loop.frame.remove()
    if (tellMod) means.loopClosed(effect)
  }

  function loop(effect, html, closeAfterMs) {
    endLoop(effect, false) // a loop played again replaces the one there
    const frame = means.frame(html)
    const timer = means.later(closeAfterMs, () => endLoop(effect, true))
    loops.set(effect, { frame, timer })
    track(frame, () => endLoop(effect, true))
  }

  return {
    play({ kind, effect, html, closeAfterMs }) {
      if (kind === "loop") loop(effect, html, closeAfterMs)
      else oneShot(html, closeAfterMs)
    },
    close: effect => endLoop(effect, false),
    stopAll() {
      for (const effect of [...loops.keys()]) endLoop(effect, false)
    },
    /** A window message: a frame's document says it is done. */
    message(source, data) {
      if (data !== CLOSE_SIGNAL) return
      byWindow.get(source)?.()
    },
    loopsPlaying: () => loops.size,
  }
}
