import type { ClientSurface, JsonValue } from 'claude-code'

type Props = { cell: string; cols: number; rows: number; vw: number; vh: number }
type State = { queue: JsonValue[] }

/**
 * The input layer over a browser cell's picture: pointer and keys, in the
 * page's own pixels, batched once a frame (a post replaces an undelivered
 * one, so a click's down and up must ride together).
 */
export default function BrowserSurface(props: Props, surface: ClientSurface<State>) {
  const { Box } = surface.elements

  if (surface.state === undefined) {
    const state: State = { queue: [] }
    surface.setState(state)
    surface.every(16, () => {
      if (state.queue.length === 0) return
      surface.post({ kind: 'input', cell: props.cell, events: state.queue.splice(0) })
    })
  }

  const queue = () => surface.state?.queue ?? []
  const toPage = (x: number, y: number) => ({
    x: Math.round((x * props.vw) / Math.max(1, props.cols)),
    y: Math.round((y * props.vh) / Math.max(1, props.rows)),
  })

  surface.onPointer(e => {
    if (e.type === 'enter' || e.type === 'leave') return
    const { x, y } = toPage(e.fine?.x ?? e.x + 0.5, e.fine?.y ?? e.y + 0.5)
    const q = queue()
    const ev = { op: 'mouse', action: e.type, x, y, button: e.button ?? 'none' }
    // Hover moves fold to the latest; downs and ups are always kept.
    const last = q[q.length - 1] as { action?: string } | undefined
    if (e.type === 'move' && last?.action === 'move') q[q.length - 1] = ev
    else q.push(ev)
  })

  surface.onKey(e => {
    queue().push({ op: 'key', key: e.key, ...(e.ctrl ? { ctrl: true } : {}), ...(e.shift ? { shift: true } : {}), ...(e.meta ? { meta: true } : {}) })
  })

  return <Box width={props.cols} height={props.rows} />
}
