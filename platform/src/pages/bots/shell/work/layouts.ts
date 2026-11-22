// Layouts and the panel stack, the way Claude's side panels work.
//
// The desk is the chat on the left and the panel area on the right. A layout
// cuts the panel area into frames (a grid, the Glyphh desktop's way: glyphh/app
// src/renderer/help/workspace-grid.ts, ported). Each frame holds a STACK of
// panels: the 1st fills the frame, the 2nd goes under it, the 3rd opens full
// as the next column, the 4th under that, and so on. Opening a panel goes to
// the pinned frame if one is pinned, else to the first empty frame, else to
// the frame holding the fewest panels. A panel already open is focused, not
// opened twice. Closing one lets the rest reflow; expanding one fills the
// whole desk until it is toggled back.
//
// Everything here is data, no DOM and no Electron: the desk, the layout
// manager and the main process all use it, and test/layouts.test.ts checks it.

/** Grids go up to 6 x 6: a window, not a wall of terminals. */
export const MAX_GRID = 6
/** A frame holds up to 8 panels (4 columns of 2); a 9th pushes out the oldest. */
export const MAX_STACK = 8
/** The chat's share of the desk when the panel area is showing. */
export const CHAT_WIDTH = 0.42

/** What a frame can hold: a work panel, or one bot's own chat ("bot:<id>"). */
export type PanelId = string

/** The main chat: always the desk's left column, never stacked in a frame. */
export const CHAT: PanelId = 'chat'

export const PANELS: ReadonlyArray<{ id: PanelId; label: string }> = Object.freeze([
  { id: 'chat', label: 'Chat' },
  { id: 'files', label: 'Files' },
  { id: 'editor', label: 'Editor' },
  { id: 'diff', label: 'Diff' },
  { id: 'browser', label: 'Browser' },
  { id: 'terminal', label: 'Terminal' }
])

export const botPanel = (botId: string): PanelId => `bot:${botId}`
export const botOfPanel = (panelId: PanelId): string | null => (panelId.startsWith('bot:') ? panelId.slice(4) : null)

/** One of your apps in a Browser panel of its own: web:<app id>:<n>, a new one each time it opens. */
export const webPanel = (appId: string, n: number): PanelId => `web:${appId}:${n}`
export const appOfPanel = (panelId: PanelId): string | null => /^web:([^:]+):\d+$/.exec(panelId)?.[1] ?? null

/** A panel id for an app that no panel in the layout uses yet. */
export function freshWebPanel(l: Grid, appId: string): PanelId {
  const used = new Set(l.frames.flatMap((f) => f.stack))
  let n = 1
  while (used.has(webPanel(appId, n))) n++
  return webPanel(appId, n)
}

/** A panel this app has (old saved data may name ones it no longer has, like the Swarm panel). */
export const isPanel = (id: PanelId): boolean =>
  PANELS.some((p) => p.id === id) || (id.startsWith('bot:') && id.length > 4) || appOfPanel(id) !== null

/** One frame of the panel area. */
export interface Frame {
  col: number
  row: number
  colSpan: number
  rowSpan: number
  /** New panels stack into a pinned frame. At most one frame is pinned. */
  pinned?: boolean
  /** Its panels in the order they opened. */
  stack: PanelId[]
}

/** The panel area's frames: every grid position covered by exactly one frame. */
export interface Grid {
  cols: number
  rows: number
  frames: Frame[]
}

/** The layout on screen. */
export interface Layout extends Grid {
  name: string
  colWidths: number[]
  rowHeights: number[]
  /** The chat's share of the desk's width (0..1). */
  chatWidth: number
}

/** A frame as a saved layout keeps it. */
export interface SavedFrame {
  col?: number
  row?: number
  colSpan?: number
  rowSpan?: number
  pinned?: boolean
  stack?: PanelId[]
}

/** A layout as it is saved: its name, its frames, their seams, pins and panels. */
export interface SavedLayout {
  name: string
  cols: number
  rows: number
  colWidths?: number[]
  rowHeights?: number[]
  chatWidth?: number
  frames: SavedFrame[]
  /** Set by the save; the built-ins have none. */
  updatedAt?: number
}

const clampDim = (n: unknown, fallback: number): number => {
  const v = Math.floor(Number(n))
  return Number.isFinite(v) && v >= 1 ? Math.min(v, MAX_GRID) : fallback
}

const clampChat = (n: unknown): number => {
  const v = Number(n)
  return Number.isFinite(v) ? Math.max(0.2, Math.min(0.8, v)) : CHAT_WIDTH
}

const cleanStack = (s: unknown): PanelId[] => {
  if (!Array.isArray(s)) return []
  const out: PanelId[] = []
  for (const p of s) {
    const id = String(p ?? '').trim()
    if (id && id !== CHAT && isPanel(id) && !out.includes(id)) out.push(id)
  }
  return out.slice(-MAX_STACK)
}

// ------------------------------------------------------------- the grid

/** A fresh grid of empty 1x1 frames. */
export function emptyGrid(cols: number, rows: number): Grid {
  const c = clampDim(cols, 1)
  const r = clampDim(rows, 1)
  const frames: Frame[] = []
  for (let y = 0; y < r; y++) for (let x = 0; x < c; x++) frames.push({ col: x, row: y, colSpan: 1, rowSpan: 1, stack: [] })
  return { cols: c, rows: r, frames }
}

/** The index of the frame covering (col, row), or -1. */
export function frameAt(g: Grid, col: number, row: number): number {
  return g.frames.findIndex((f) => col >= f.col && col < f.col + f.colSpan && row >= f.row && row < f.row + f.rowSpan)
}

const covers = (o: Frame, x: number, y: number): boolean => x >= o.col && x < o.col + o.colSpan && y >= o.row && y < o.row + o.rowSpan

/**
 * Saved frames -> a whole grid: each saved frame laid on its top-left with its
 * spans, pin and stack; positions nothing covers become empty 1x1s. Spans are
 * clamped to the edges; a frame outside the grid, or one landing on an earlier
 * frame, is skipped; a panel is kept in one frame only; one pin at most.
 */
export function gridFromFrames(cols: number, rows: number, saved: ReadonlyArray<SavedFrame>): Grid {
  const g = emptyGrid(cols, rows)
  const placed: Frame[] = []
  const seen = new Set<PanelId>()
  let pinned = false
  for (const s of saved) {
    if (!s || typeof s !== 'object') continue
    const col = Math.floor(Number(s.col ?? 0))
    const row = Math.floor(Number(s.row ?? 0))
    if (!(col >= 0 && col < g.cols && row >= 0 && row < g.rows)) continue
    const f: Frame = {
      col,
      row,
      colSpan: Math.max(1, Math.min(Math.floor(Number(s.colSpan ?? 1)) || 1, g.cols - col)),
      rowSpan: Math.max(1, Math.min(Math.floor(Number(s.rowSpan ?? 1)) || 1, g.rows - row)),
      stack: cleanStack(s.stack).filter((p) => !seen.has(p))
    }
    let overlaps = false
    for (let y = f.row; y < f.row + f.rowSpan && !overlaps; y++)
      for (let x = f.col; x < f.col + f.colSpan; x++) if (placed.some((o) => covers(o, x, y))) overlaps = true
    if (overlaps) continue
    f.stack.forEach((p) => seen.add(p))
    if (s.pinned && !pinned) {
      f.pinned = true
      pinned = true
    }
    placed.push(f)
  }
  const rest = g.frames.filter((e) => !placed.some((o) => covers(o, e.col, e.row)))
  g.frames = [...placed, ...rest].sort((a, b) => a.row - b.row || a.col - b.col)
  return g
}

/** Resize in place: frames whose anchor still fits stay (spans clamped); new positions arrive empty. */
export function resizeGrid(g: Grid, cols: number, rows: number): void {
  g.cols = clampDim(cols, g.cols)
  g.rows = clampDim(rows, g.rows)
  const kept: Frame[] = []
  for (const f of g.frames) {
    if (f.col >= g.cols || f.row >= g.rows) continue
    f.colSpan = Math.min(f.colSpan, g.cols - f.col)
    f.rowSpan = Math.min(f.rowSpan, g.rows - f.row)
    kept.push(f)
  }
  g.frames = kept
  for (let y = 0; y < g.rows; y++)
    for (let x = 0; x < g.cols; x++) if (frameAt(g, x, y) === -1) g.frames.push({ col: x, row: y, colSpan: 1, rowSpan: 1, stack: [] })
  g.frames.sort((a, b) => a.row - b.row || a.col - b.col)
}

/** The frame to the right is ONE frame with this frame's row range. */
export function canMergeRight(g: Grid, idx: number): boolean {
  const f = g.frames[idx]
  if (!f || f.col + f.colSpan >= g.cols) return false
  const r = g.frames[frameAt(g, f.col + f.colSpan, f.row)]
  return !!r && r.col === f.col + f.colSpan && r.row === f.row && r.rowSpan === f.rowSpan
}

/** The frame below is ONE frame with this frame's column range. */
export function canMergeDown(g: Grid, idx: number): boolean {
  const f = g.frames[idx]
  if (!f || f.row + f.rowSpan >= g.rows) return false
  const b = g.frames[frameAt(g, f.col, f.row + f.rowSpan)]
  return !!b && b.row === f.row + f.rowSpan && b.col === f.col && b.colSpan === f.colSpan
}

export const canSplit = (g: Grid, idx: number): boolean => {
  const f = g.frames[idx]
  return !!f && (f.colSpan > 1 || f.rowSpan > 1)
}

function absorb(g: Grid, idx: number, otherIdx: number): number {
  const f = g.frames[idx]!
  const o = g.frames[otherIdx]!
  f.stack = [...f.stack, ...o.stack].slice(-MAX_STACK)
  if (o.pinned) f.pinned = true
  g.frames.splice(otherIdx, 1)
  return g.frames.indexOf(f)
}

/** Merge with the right neighbour (its panels join this frame). Returns the merged frame's index. */
export function mergeRight(g: Grid, idx: number): number {
  if (!canMergeRight(g, idx)) return idx
  const f = g.frames[idx]!
  const r = frameAt(g, f.col + f.colSpan, f.row)
  f.colSpan += g.frames[r]!.colSpan
  return absorb(g, idx, r)
}

/** Merge with the frame below (its panels join this frame). Returns the merged frame's index. */
export function mergeDown(g: Grid, idx: number): number {
  if (!canMergeDown(g, idx)) return idx
  const f = g.frames[idx]!
  const b = frameAt(g, f.col, f.row + f.rowSpan)
  f.rowSpan += g.frames[b]!.rowSpan
  return absorb(g, idx, b)
}

/** Split a merged frame into 1x1s; its panels and pin stay on the top-left piece. */
export function splitFrame(g: Grid, idx: number): void {
  const f = g.frames[idx]
  if (!f || (f.colSpan === 1 && f.rowSpan === 1)) return
  const pieces: Frame[] = []
  for (let y = f.row; y < f.row + f.rowSpan; y++)
    for (let x = f.col; x < f.col + f.colSpan; x++)
      pieces.push(
        y === f.row && x === f.col
          ? { col: x, row: y, colSpan: 1, rowSpan: 1, stack: f.stack, ...(f.pinned ? { pinned: true } : {}) }
          : { col: x, row: y, colSpan: 1, rowSpan: 1, stack: [] }
      )
  g.frames.splice(idx, 1, ...pieces)
}

/** Pin exactly one frame, or unpin it. */
export function setPinned(g: Grid, idx: number, on: boolean): void {
  g.frames.forEach((f, i) => {
    if (on && i === idx) f.pinned = true
    else delete f.pinned
  })
}

/** Frame indices in reading order: top row left to right, then down. */
export function readingOrder(g: Grid): number[] {
  return g.frames.map((_, i) => i).sort((a, b) => g.frames[a]!.row - g.frames[b]!.row || g.frames[a]!.col - g.frames[b]!.col)
}

export type DropMode = 'before' | 'after' | 'swap'

/** Where in a frame the pointer is: the leading edge inserts before, the trailing edge after, the middle swaps. */
export function dropModeAt(fx: number, fy: number): DropMode {
  if (fx < 0.28 || fy < 0.28) return 'before'
  if (fx > 0.72 || fy > 0.72) return 'after'
  return 'swap'
}

/**
 * A frame dragged onto another in the layout manager. Contents (panels and
 * pin) move, geometry stays: the middle SWAPS two frames' contents; an edge
 * INSERTS the dragged contents before or after the target in reading order.
 */
export function applyDrop(g: Grid, fromIdx: number, toIdx: number, mode: DropMode): void {
  if (fromIdx === toIdx || !g.frames[fromIdx] || !g.frames[toIdx]) return
  type Contents = { stack: PanelId[]; pinned?: boolean }
  const order = readingOrder(g)
  const contents: Contents[] = order.map((i) => ({ stack: g.frames[i]!.stack, pinned: g.frames[i]!.pinned }))
  const src = order.indexOf(fromIdx)
  let dst = order.indexOf(toIdx)
  if (mode === 'swap') {
    ;[contents[src], contents[dst]] = [contents[dst]!, contents[src]!]
  } else {
    const [moved] = contents.splice(src, 1)
    if (src < dst) dst--
    contents.splice(mode === 'before' ? dst : dst + 1, 0, moved!)
  }
  order.forEach((i, p) => {
    const f = g.frames[i]!
    f.stack = contents[p]!.stack
    if (contents[p]!.pinned) f.pinned = true
    else delete f.pinned
  })
}

/** The frames a save writes, in reading order. */
export function savedFrames(g: Grid): SavedFrame[] {
  return readingOrder(g).map((i) => {
    const f = g.frames[i]!
    return {
      col: f.col,
      row: f.row,
      colSpan: f.colSpan,
      rowSpan: f.rowSpan,
      ...(f.pinned ? { pinned: true } : {}),
      stack: f.stack.slice()
    }
  })
}

/** n equal fractions. */
export const evenFractions = (n: number): number[] => Array.from({ length: Math.max(1, n) }, () => 1 / Math.max(1, n))

/** The layout's own seams when the count is unchanged, else even ones. */
export function fractionsFor(prev: ReadonlyArray<number> | null | undefined, n: number): number[] {
  return prev && prev.length === n && prev.every((v) => Number.isFinite(v) && v > 0) ? prev.slice() : evenFractions(n)
}

/** Move the seam after column (or row) i to `pos` (0..1 across the whole grid); each side keeps at least 8%. */
export function moveSeam(fractions: ReadonlyArray<number>, i: number, pos: number): number[] {
  const arr = fractions.slice()
  if (i < 0 || i >= arr.length - 1) return arr
  const total = arr.reduce((a, b) => a + b, 0)
  const pair = arr[i]! + arr[i + 1]!
  const before = arr.slice(0, i).reduce((a, b) => a + b, 0)
  const want = Math.max(0.08 * total, Math.min(pair - 0.08 * total, pos * total - before))
  arr[i] = +want.toFixed(4)
  arr[i + 1] = +(pair - want).toFixed(4)
  return arr
}

// ------------------------------------------------------- the stack

/** The frame a panel is in, or -1. */
export const frameOf = (l: Grid, panelId: PanelId): number => l.frames.findIndex((f) => f.stack.includes(panelId))

/** Every panel open in the layout, frame by frame. */
export const openPanels = (l: Grid): PanelId[] => readingOrder(l).flatMap((i) => l.frames[i]!.stack)

export const cloneLayout = (l: Layout): Layout => ({
  ...l,
  colWidths: l.colWidths.slice(),
  rowHeights: l.rowHeights.slice(),
  frames: l.frames.map((f) => ({ ...f, stack: f.stack.slice() }))
})

/**
 * Where a newly opened panel goes: the pinned frame; else it joins the first
 * frame already showing panels (so panels go full, under, full, under in one
 * run); else the first empty frame; else the one with fewest panels.
 */
export function targetFrame(l: Grid): number {
  const pinned = l.frames.findIndex((f) => f.pinned)
  if (pinned >= 0) return pinned
  const order = readingOrder(l)
  const showing = order.find((i) => l.frames[i]!.stack.length > 0 && l.frames[i]!.stack.length < MAX_STACK)
  if (showing !== undefined) return showing
  const empty = order.find((i) => !l.frames[i]!.stack.length)
  if (empty !== undefined) return empty
  let best = order[0]!
  for (const i of order) if (l.frames[i]!.stack.length < l.frames[best]!.stack.length) best = i
  return best
}

export type Opened =
  | { how: 'chat'; layout: Layout }
  | { how: 'already'; layout: Layout; frame: number }
  | { how: 'pinned' | 'empty' | 'stack'; layout: Layout; frame: number; dropped?: PanelId }

/**
 * Open a panel: the chat is the desk's own column; a panel already open is
 * focused where it is; anything else stacks into targetFrame (or `into`, a
 * frame picked by hand). A full frame lets its oldest panel go.
 */
export function openPanel(l: Layout, panelId: PanelId, into?: number): Opened {
  if (panelId === CHAT) return { how: 'chat', layout: l }
  const at = frameOf(l, panelId)
  if (at >= 0 && (into === undefined || into === at)) return { how: 'already', layout: l, frame: at }
  const next = cloneLayout(l)
  if (at >= 0) next.frames[at]!.stack = next.frames[at]!.stack.filter((p) => p !== panelId)
  const frame = into !== undefined && next.frames[into] ? into : targetFrame(next)
  const f = next.frames[frame]!
  const how = into !== undefined ? 'stack' : f.pinned ? 'pinned' : f.stack.length ? 'stack' : 'empty'
  f.stack.push(panelId)
  const dropped = f.stack.length > MAX_STACK ? f.stack.shift() : undefined
  return { how, layout: next, frame, ...(dropped ? { dropped } : {}) }
}

/** Close a panel; the rest of its frame reflows to fill. */
export function closePanel(l: Layout, panelId: PanelId): Layout {
  const next = cloneLayout(l)
  for (const f of next.frames) f.stack = f.stack.filter((p) => p !== panelId)
  return next
}

/** Same frames, no panels (a layout picked from the list keeps the panels you have open). */
export function withPanels(l: Layout, open: ReadonlyArray<PanelId>): Layout {
  let next = cloneLayout(l)
  for (const p of open) {
    if (frameOf(next, p) >= 0) continue
    const o = openPanel(next, p)
    next = o.layout
  }
  return next
}

// ------------------------------------------------------- geometry

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

/**
 * Where a frame's n panels sit inside it (fractions of the frame): column c
 * holds panels 2c and 2c+1; one panel fills its column, two split it top and
 * bottom. So: full, under, full, under.
 */
export function stackSlots(n: number): Rect[] {
  const cols = Math.ceil(n / 2)
  const out: Rect[] = []
  for (let i = 0; i < n; i++) {
    const c = Math.floor(i / 2)
    const pair = 2 * c + 1 < n
    out.push({ x: c / cols, y: pair && i % 2 ? 0.5 : 0, w: 1 / cols, h: pair ? 0.5 : 1 })
  }
  return out
}

const sum = (a: ReadonlyArray<number>, n = a.length): number => a.slice(0, n).reduce((s, v) => s + v, 0)

export interface DeskRects {
  /** The chat's place, or null while another panel is expanded. */
  chat: Rect | null
  /** The panel area (empty when it is not showing). */
  area: Rect | null
  frames: { idx: number; rect: Rect }[]
  /** Every open panel; hidden ones stay mounted so they keep their state. */
  panels: { panelId: PanelId; frame: number; rect: Rect; hidden: boolean }[]
  /** The frames on screen are the layout's own (none collapsed), so its seams can be dragged. */
  exact: boolean
}

/**
 * The desk's geometry (fractions of the desk): the chat on the left, the
 * panel area on the right. What shows comes only from the panels that are
 * open: no panel, the chat has the whole width; empty frames are never drawn.
 * A frame's stack lies full / under / full / under. A layout's columns and
 * rows that hold no open panel collapse away (the rest take their space); if
 * an empty frame would still leave a hole, every open panel is laid out as
 * one stack across the whole area instead. `minChat` keeps the chat at least
 * that share of the desk; `expanded` fills the whole desk with one panel.
 */
export function deskRects(l: Layout, expanded: PanelId | null = null, hideArea = false, minChat = 0): DeskRects {
  // An empty frame next to a used one of the same width (or height) is taken
  // over by it: Files over an emptied Diff fills the whole column.
  const eff = l.frames.map((f) => ({ ...f }))
  let grew = true
  while (grew) {
    grew = false
    for (let e = 0; e < eff.length; e++) {
      const g = eff[e]!
      if (g.stack.length || g.colSpan === 0) continue
      const by = eff.findIndex(
        (f) =>
          f.stack.length > 0 &&
          ((f.col === g.col && f.colSpan === g.colSpan && (f.row + f.rowSpan === g.row || g.row + g.rowSpan === f.row)) ||
            (f.row === g.row && f.rowSpan === g.rowSpan && (f.col + f.colSpan === g.col || g.col + g.colSpan === f.col)))
      )
      if (by < 0) continue
      const f = eff[by]!
      if (f.col === g.col && f.colSpan === g.colSpan) {
        const top = Math.min(f.row, g.row)
        f.rowSpan += g.rowSpan
        f.row = top
      } else {
        const left = Math.min(f.col, g.col)
        f.colSpan += g.colSpan
        f.col = left
      }
      g.colSpan = 0 // absorbed
      grew = true
    }
  }
  const live = eff.filter((f) => f.colSpan > 0)
  const used = eff.map((f, i) => ({ f, i })).filter((x) => x.f.stack.length > 0)
  const showArea = !hideArea && used.length > 0
  const chatW = showArea ? Math.min(0.75, Math.max(l.chatWidth, minChat)) : 1
  const area: Rect = { x: chatW, y: 0, w: 1 - chatW, h: 1 }
  const covers = (f: Frame, c: number, r: number): boolean => c >= f.col && c < f.col + f.colSpan && r >= f.row && r < f.row + f.rowSpan
  const colUsed = l.colWidths.map((_, c) => used.some(({ f }) => c >= f.col && c < f.col + f.colSpan))
  const rowUsed = l.rowHeights.map((_, r) => used.some(({ f }) => r >= f.row && r < f.row + f.rowSpan))
  const hole = live.some(
    (f) => !f.stack.length && colUsed.some((cu, c) => cu && rowUsed.some((ru, r) => ru && covers(f, c, r)))
  )
  const exact = used.length === l.frames.length
  const panels: DeskRects['panels'] = []
  let frames: DeskRects['frames'] = []
  const place = (fr: Rect, stack: PanelId[], frameOfK: (k: number) => number): void =>
    stackSlots(stack.length).forEach((s, k) =>
      panels.push({
        panelId: stack[k]!,
        frame: frameOfK(k),
        rect: { x: fr.x + s.x * fr.w, y: fr.y + s.y * fr.h, w: s.w * fr.w, h: s.h * fr.h },
        hidden: !showArea
      })
    )
  if (hole) {
    // One stack over the whole area, in the frames' order.
    const all = used.flatMap(({ f, i }) => f.stack.map((p) => ({ p, i })))
    place(area, all.map((x) => x.p), (k) => all[k]!.i)
  } else {
    const cw = l.colWidths.map((w, c) => (colUsed[c] ? w : 0))
    const rh = l.rowHeights.map((h, r) => (rowUsed[r] ? h : 0))
    const tw = sum(cw) || 1
    const th = sum(rh) || 1
    frames = used.map(({ f, i }) => ({
      idx: i,
      rect: {
        x: area.x + (area.w * sum(cw, f.col)) / tw,
        y: area.y + (area.h * sum(rh, f.row)) / th,
        w: (area.w * sum(cw.slice(f.col, f.col + f.colSpan))) / tw,
        h: (area.h * sum(rh.slice(f.row, f.row + f.rowSpan))) / th
      }
    }))
    for (const fr of frames) place(fr.rect, l.frames[fr.idx]!.stack, () => fr.idx)
  }
  const full: Rect = { x: 0, y: 0, w: 1, h: 1 }
  if (expanded && expanded !== CHAT && panels.some((p) => p.panelId === expanded)) {
    for (const p of panels) {
      if (p.panelId === expanded) {
        p.rect = full
        p.hidden = false
      } else p.hidden = true
    }
    return { chat: null, area: null, frames: [], panels, exact }
  }
  if (expanded === CHAT) {
    for (const p of panels) p.hidden = true
    return { chat: full, area: null, frames: [], panels, exact }
  }
  return { chat: { x: 0, y: 0, w: chatW, h: 1 }, area: showArea ? area : null, frames: showArea ? frames : [], panels, exact }
}

export interface Seam {
  dir: 'v' | 'h'
  /** The seam after column (or row) i. */
  i: number
  /** Its place in the panel area (fractions of the area). */
  rect: Rect
}

/** The seams between frames that really meet: a frame spanning two rows has no row seam across it. */
export function frameSeams(l: Layout): Seam[] {
  const out: Seam[] = []
  const tw = sum(l.colWidths) || 1
  const th = sum(l.rowHeights) || 1
  const meets = (dir: 'v' | 'h', i: number, at: number): boolean => {
    const ends = l.frames.some((f) =>
      dir === 'v' ? f.col + f.colSpan - 1 === i && at >= f.row && at < f.row + f.rowSpan : f.row + f.rowSpan - 1 === i && at >= f.col && at < f.col + f.colSpan
    )
    const starts = l.frames.some((f) =>
      dir === 'v' ? f.col === i + 1 && at >= f.row && at < f.row + f.rowSpan : f.row === i + 1 && at >= f.col && at < f.col + f.colSpan
    )
    return ends && starts
  }
  for (let i = 0; i < l.cols - 1; i++)
    for (let at = 0; at < l.rows; at++)
      if (meets('v', i, at)) out.push({ dir: 'v', i, rect: { x: sum(l.colWidths, i + 1) / tw, y: sum(l.rowHeights, at) / th, w: 0, h: l.rowHeights[at]! / th } })
  for (let i = 0; i < l.rows - 1; i++)
    for (let at = 0; at < l.cols; at++)
      if (meets('h', i, at)) out.push({ dir: 'h', i, rect: { x: sum(l.colWidths, at) / tw, y: sum(l.rowHeights, i + 1) / th, w: l.colWidths[at]! / tw, h: 0 } })
  return out
}

// ------------------------------------------------------- saved layouts

const frame = (col: number, row: number, stack: PanelId[] = [], rowSpan = 1, colSpan = 1): SavedFrame => ({ col, row, colSpan, rowSpan, stack })

/** The layouts every install has. The first one is where the app starts. */
export const BUILTIN_LAYOUTS: ReadonlyArray<SavedLayout> = Object.freeze([
  { name: 'Default', cols: 1, rows: 1, frames: [frame(0, 0)] },
  { name: 'Side by side', cols: 2, rows: 1, frames: [frame(0, 0), frame(1, 0)] },
  {
    name: 'Dev',
    cols: 3,
    rows: 2,
    chatWidth: 0.26,
    colWidths: [0.24, 0.4, 0.36],
    rowHeights: [0.55, 0.45],
    frames: [frame(0, 0, ['files']), frame(0, 1, ['diff']), frame(1, 0, ['editor'], 2), frame(2, 0, ['browser'], 2)]
  },
  { name: 'Review', cols: 2, rows: 1, chatWidth: 0.3, colWidths: [0.45, 0.55], frames: [frame(0, 0, ['diff']), frame(1, 0, ['editor'])] }
])

/** The empty shapes a new layout can start from. */
export const SHAPES: ReadonlyArray<{ name: string; cols: number; rows: number; merge?: Array<[number, 'right' | 'down']> }> = Object.freeze([
  { name: 'Single', cols: 1, rows: 1 },
  { name: 'Split', cols: 2, rows: 1 },
  { name: 'Thirds', cols: 3, rows: 1 },
  { name: 'Stack', cols: 1, rows: 2 },
  { name: 'Grid 2x2', cols: 2, rows: 2 },
  { name: 'Main and two', cols: 2, rows: 2, merge: [[0, 'down']] }
])

const key = (name: string): string => name.trim().toLowerCase()

export const isBuiltin = (name: string): boolean => BUILTIN_LAYOUTS.some((l) => key(l.name) === key(name))

/** Every layout you can open: the built-ins, then yours. */
export function allLayouts(saved: ReadonlyArray<SavedLayout>): SavedLayout[] {
  return [...BUILTIN_LAYOUTS, ...saved.filter((l) => !isBuiltin(l.name))]
}

export function findLayout(saved: ReadonlyArray<SavedLayout>, name: string): SavedLayout | undefined {
  return allLayouts(saved).find((l) => key(l.name) === key(name))
}

/** A saved layout -> the layout on screen. */
export function openLayout(s: SavedLayout): Layout {
  const g = gridFromFrames(s.cols, s.rows, s.frames)
  return {
    name: s.name,
    ...g,
    colWidths: fractionsFor(s.colWidths, g.cols),
    rowHeights: fractionsFor(s.rowHeights, g.rows),
    chatWidth: clampChat(s.chatWidth)
  }
}

/** The layout on screen -> what a save keeps (its pins and the panels open in it). */
export function toSaved(l: Layout, name = l.name): SavedLayout {
  return {
    name: name.trim(),
    cols: l.cols,
    rows: l.rows,
    colWidths: fractionsFor(l.colWidths, l.cols),
    rowHeights: fractionsFor(l.rowHeights, l.rows),
    chatWidth: clampChat(l.chatWidth),
    frames: savedFrames(l)
  }
}

/** Why a layout can't be saved under its name, or null. */
export function saveError(l: SavedLayout, replacing?: string): string | null {
  if (!l.name.trim()) return 'Give the layout a name.'
  if (isBuiltin(l.name) && !(replacing && key(replacing) === key(l.name) && !isBuiltin(replacing)))
    return `"${l.name.trim()}" is a built-in layout. Pick another name.`
  return null
}

/** A saved record, cleaned: its frames read back through the grid so spans, pins and stacks are valid. */
function clean(l: Partial<SavedLayout> & { name: string }, updatedAt?: number): SavedLayout {
  const cols = clampDim(l.cols, 1)
  const rows = clampDim(l.rows, 1)
  return {
    name: l.name.trim(),
    cols,
    rows,
    colWidths: fractionsFor(l.colWidths, cols),
    rowHeights: fractionsFor(l.rowHeights, rows),
    chatWidth: clampChat(l.chatWidth),
    frames: savedFrames(gridFromFrames(cols, rows, l.frames ?? [])),
    ...(typeof updatedAt === 'number' ? { updatedAt } : {})
  }
}

/**
 * Save a layout into the list: one with the same name (any case) is replaced
 * in place; `replacing` names the one being edited, so a rename drops the old
 * name. Throws the reason when it can't be saved.
 */
export function saveLayout(list: ReadonlyArray<SavedLayout>, l: SavedLayout, replacing?: string, now = Date.now()): SavedLayout[] {
  const err = saveError(l, replacing)
  if (err) throw new Error(err)
  const rec = clean(l, now)
  const out = list.filter((x) => !(replacing && key(x.name) === key(replacing) && key(replacing) !== key(rec.name)))
  const i = out.findIndex((x) => key(x.name) === key(rec.name))
  if (i >= 0) out[i] = rec
  else out.push(rec)
  return out
}

/** Remove one of your layouts (a built-in can't be removed). */
export function removeLayout(list: ReadonlyArray<SavedLayout>, name: string): SavedLayout[] {
  return list.filter((x) => key(x.name) !== key(name))
}

/** The first version kept one panel per cell ({cells: [{panelId, sticky}]}); read it as frames. */
function fromOldCells(r: Record<string, unknown>): SavedFrame[] | undefined {
  if (Array.isArray(r.frames)) return r.frames as SavedFrame[]
  if (!Array.isArray(r.cells)) return undefined
  return (r.cells as Record<string, unknown>[]).map((c) => ({
    col: c?.col as number,
    row: c?.row as number,
    colSpan: c?.colSpan as number,
    rowSpan: c?.rowSpan as number,
    pinned: !!c?.sticky,
    stack: typeof c?.panelId === 'string' ? [c.panelId] : []
  }))
}

/** Saved data read back from disk: anything malformed is dropped. */
export function normalizeSaved(raw: unknown): SavedLayout[] {
  if (!Array.isArray(raw)) return []
  const out: SavedLayout[] = []
  for (const r of raw) {
    if (!r || typeof r !== 'object') continue
    const o = r as Record<string, unknown>
    const frames = fromOldCells(o)
    if (typeof o.name !== 'string' || !o.name.trim() || !frames) continue
    if (isBuiltin(o.name) || out.some((x) => key(x.name) === key(o.name as string))) continue
    out.push(clean({ ...(o as Partial<SavedLayout>), name: o.name, frames }, typeof o.updatedAt === 'number' ? o.updatedAt : undefined))
  }
  return out
}

/** The layout on screen read back from disk, or null. */
export function normalizeCurrent(raw: unknown): Layout | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const frames = fromOldCells(o)
  if (!frames) return null
  return openLayout({ ...(o as Partial<SavedLayout>), name: typeof o.name === 'string' ? o.name : 'Layout', frames } as SavedLayout)
}

/** Whether the layout on screen still has a saved layout's frames and pins (panels come and go). */
export function sameShape(a: SavedLayout, b: SavedLayout): boolean {
  const sig = (l: SavedLayout): string =>
    `${l.cols}x${l.rows}:` +
    savedFrames(gridFromFrames(l.cols, l.rows, l.frames))
      .map((f) => `${f.col},${f.row},${f.colSpan},${f.rowSpan}${f.pinned ? 'p' : ''}`)
      .join('|')
  return sig(a) === sig(b)
}
