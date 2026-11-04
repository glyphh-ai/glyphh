// A layout's grid: the rules of the desktop app's layout editor (glyphh-ai/desktop,
// help/workspace-grid.ts), for what Claude's window holds. Every position of a cols × rows grid is covered by
// exactly one cell; a merged cell is stored by its top-left with its spans; pane '' is an empty cell, and a pane
// sits in one cell at most. Two differences: a grid is at most 4 × 4 (there are nine things to place, not a wall of
// terminals), and it stays cuttable by straight lines (`cuts`), which is what lets a pane draw it with rows of boxes.
import type { DipCell, DipCellPane, DipGrid, DipPane } from '../../types'

export const MAX_GRID = 4

const copy = (g: DipGrid): DipGrid => ({ ...g, cells: g.cells.map(c => ({ ...c })) })

const within = (n: unknown, fallback: number) => {
  const v = Math.floor(Number(n))
  return Number.isFinite(v) && v >= 1 ? Math.min(v, MAX_GRID) : fallback
}

const order = (cells: DipCell[]) => [...cells].sort((a, b) => a.row - b.row || a.col - b.col)

export function emptyGrid(cols: number, rows: number): DipGrid {
  const c = within(cols, 2)
  const r = within(rows, 1)
  const cells: DipCell[] = []
  for (let row = 0; row < r; row++) for (let col = 0; col < c; col++) cells.push({ pane: '', col, row, colSpan: 1, rowSpan: 1 })
  return { cols: c, rows: r, cells }
}

/** The cell covering (col, row), as an index, or -1. */
export function cellAt(g: DipGrid, col: number, row: number): number {
  return g.cells.findIndex(c => col >= c.col && col < c.col + c.colSpan && row >= c.row && row < c.row + c.rowSpan)
}

/** The side panes in reading order: the order a dip shows them. */
export const panesOf = (g: DipGrid): DipPane[] =>
  order(g.cells).flatMap(c => (c.pane && c.pane !== 'claude' ? [c.pane] : []))

/** The order a dip opens the side panes: down each column, left to right. The app places a pane by when it opens, and
 *  fills a column before starting the next. */
export const openOrder = (g: DipGrid): DipPane[] =>
  [...g.cells].sort((a, b) => a.col - b.col || a.row - b.row).flatMap(c => (c.pane && c.pane !== 'claude' ? [c.pane] : []))

/** A tile as the app's Move handles know it: a pane, or Claude. */
const tileOf = (pane: DipCellPane) => (pane === 'claude' ? 'chat' : pane)

export type Edge = 'left' | 'right' | 'top' | 'bottom'

/** The grid as tiles taken off its outside, one at a time, outermost first, down to the last tile: how a dip builds it,
 *  since a move to an edge of the window spans all the rest. `shown` leaves out panes that did not open; Claude,
 *  always open, goes down the left of a grid without it. Null for a shape with no tile to take off, as a plain 2 × 2. */
export function peels(g: DipGrid, shown: readonly DipPane[]): { tile: string; edge: Edge }[] | null {
  let cells = g.cells.filter(c => c.pane === 'claude' || (c.pane !== '' && shown.includes(c.pane)))
  const out: { tile: string; edge: Edge }[] = cells.some(c => c.pane === 'claude') ? [] : [{ tile: 'chat', edge: 'left' }]
  while (cells.length > 1) {
    const rest = (c: DipCell) => cells.filter(x => x !== c)
    const left = Math.min(...cells.map(c => c.col))
    const top = Math.min(...cells.map(c => c.row))
    const right = Math.max(...cells.map(c => c.col + c.colSpan))
    const bottom = Math.max(...cells.map(c => c.row + c.rowSpan))
    const tall = (c: DipCell) => c.row <= top && c.row + c.rowSpan >= bottom
    const wide = (c: DipCell) => c.col <= left && c.col + c.colSpan >= right
    const off = cells.flatMap(c => {
      if (tall(c) && rest(c).every(x => x.col >= c.col + c.colSpan)) return [{ c, edge: 'left' as const }]
      if (tall(c) && rest(c).every(x => x.col + x.colSpan <= c.col)) return [{ c, edge: 'right' as const }]
      if (wide(c) && rest(c).every(x => x.row >= c.row + c.rowSpan)) return [{ c, edge: 'top' as const }]
      if (wide(c) && rest(c).every(x => x.row + x.rowSpan <= c.row)) return [{ c, edge: 'bottom' as const }]
      return []
    })[0]
    if (!off) return null
    out.push({ tile: tileOf(off.c.pane), edge: off.edge })
    cells = rest(off.c)
  }
  return out
}

/** The keys for each Move handle, innermost tile first, each move then spanning all that came before. Two arrows
 *  across a stack take a tile to the window's edge; from there one arrow along that edge takes it to the side. */
export function moves(off: readonly { tile: string; edge: Edge }[]): { tile: string; keys: string[] }[] {
  return [...off].reverse().flatMap(({ tile, edge }) => {
    if (edge === 'top') return [{ tile, keys: ['up', 'up', 'enter'] }]
    if (edge === 'bottom') return [{ tile, keys: ['down', 'down', 'enter'] }]
    return [{ tile, keys: ['down', 'down', 'enter'] }, { tile, keys: [edge, 'enter'] }]
  })
}

/** Where a tile ended up: x, y, width, height. */
export type Rect = [number, number, number, number]

/** Whether the tiles sit as the grid says: each left of and above what it should be. Tiles not measured are let by. */
export function arranged(g: DipGrid, rects: Record<string, Rect>): boolean {
  const slack = 30
  return g.cells.every(a =>
    g.cells.every(b => {
      const ra = rects[tileOf(a.pane)]
      const rb = rects[tileOf(b.pane)]
      if (!a.pane || !b.pane || !ra || !rb) return true
      if (a.col + a.colSpan <= b.col && ra[0] + ra[2] > rb[0] + slack) return false
      return !(a.row + a.rowSpan <= b.row && ra[1] + ra[3] > rb[1] + slack)
    }),
  )
}

/** The grid tiles on screen make, for /dip save: their edges become the lines; null if it won't fit or isn't whole. */
export function gridOfRects(rects: Record<string, Rect>, known: readonly string[]): DipGrid | null {
  const lines = (values: number[]) => {
    const out: number[] = []
    for (const v of [...values].sort((a, b) => a - b)) if (!out.length || v - out[out.length - 1]! > 30) out.push(v)
    return out
  }
  const all = Object.values(rects)
  const xs = lines(all.flatMap(r => [r[0], r[0] + r[2]]))
  const ys = lines(all.flatMap(r => [r[1], r[1] + r[3]]))
  const at = (edges: number[], v: number) => edges.reduce((best, e, i) => (Math.abs(e - v) < Math.abs(edges[best]! - v) ? i : best), 0)
  const cells = Object.entries(rects).map(([tile, r]) => {
    const col = at(xs, r[0])
    const row = at(ys, r[1])
    return { pane: tile === 'chat' ? 'claude' : tile, col, row, colSpan: at(xs, r[0] + r[2]) - col, rowSpan: at(ys, r[1] + r[3]) - row }
  })
  return asGrid({ cols: xs.length - 1, rows: ys.length - 1, cells }, known)
}

/** Claude down the left and the panes beside it, in the order given: a layout from before grids, or a capture. */
export function gridOfPanes(panes: readonly DipPane[]): DipGrid {
  if (!panes.length) return { cols: 1, rows: 1, cells: [{ pane: 'claude', col: 0, row: 0, colSpan: 1, rowSpan: 1 }] }
  const rows = Math.min(panes.length, 3)
  const cols = Math.ceil(panes.length / rows)
  const cells: DipCell[] = [{ pane: 'claude', col: 0, row: 0, colSpan: 1, rowSpan: rows }]
  for (let i = 0; i < rows * cols; i++) cells.push({ pane: panes[i] ?? '', col: 1 + (i % cols), row: Math.floor(i / cols), colSpan: 1, rowSpan: 1 })
  return { cols: cols + 1, rows, cells }
}

/** Part of a grid, as a pane draws it: one cell, or parts side by side (`across`) or stacked. */
export type Cut = { cell: number; rows: number } | { across: boolean; parts: { share: number; cut: Cut }[] }

/** The grid as straight cuts, or null for a pinwheel no straight line divides. */
export function cuts(g: DipGrid): Cut | null {
  const inside = (x: number, y: number, w: number, h: number) =>
    g.cells.map((c, i) => ({ c, i })).filter(({ c }) => c.col >= x && c.col < x + w && c.row >= y && c.row < y + h)
  const part = (x: number, y: number, w: number, h: number): Cut | null => {
    const here = inside(x, y, w, h)
    if (here.length === 1) return { cell: here[0]!.i, rows: h }
    const lines = (from: number, size: number, crosses: (at: number) => boolean) => {
      const at = [from]
      for (let n = from + 1; n < from + size; n++) if (!crosses(n)) at.push(n)
      return [...at, from + size]
    }
    const down = lines(x, w, n => here.some(({ c }) => c.col < n && c.col + c.colSpan > n))
    const flat = lines(y, h, n => here.some(({ c }) => c.row < n && c.row + c.rowSpan > n))
    const across = down.length > 2
    const edges = across ? down : flat
    if (edges.length <= 2) return null
    const parts: { share: number; cut: Cut }[] = []
    for (let i = 0; i + 1 < edges.length; i++) {
      const a = edges[i]!
      const size = edges[i + 1]! - a
      const cut = across ? part(a, y, size, h) : part(x, a, w, size)
      if (!cut) return null
      parts.push({ share: size / (across ? w : h), cut })
    }
    return { across, parts }
  }
  return part(0, 0, g.cols, g.rows)
}

/** A grid as the store holds it, or null when it is not whole. */
export function asGrid(v: unknown, known: readonly string[]): DipGrid | null {
  const o = (v ?? {}) as Record<string, unknown>
  if (!Array.isArray(o.cells)) return null
  const cols = Number(o.cols)
  const rows = Number(o.rows)
  if (!Number.isInteger(cols) || !Number.isInteger(rows) || cols < 1 || rows < 1 || cols > MAX_GRID || rows > MAX_GRID) return null
  const cells = o.cells.map(x => {
    const c = (x ?? {}) as Record<string, unknown>
    const pane = typeof c.pane === 'string' && known.includes(c.pane) ? (c.pane as DipCellPane) : ''
    return { pane, col: Number(c.col), row: Number(c.row), colSpan: Number(c.colSpan), rowSpan: Number(c.rowSpan) }
  })
  const seen = new Set<string>()
  for (const c of cells) {
    if (![c.col, c.row, c.colSpan, c.rowSpan].every(Number.isInteger) || c.col < 0 || c.row < 0 || c.colSpan < 1 || c.rowSpan < 1) return null
    if (c.col + c.colSpan > cols || c.row + c.rowSpan > rows) return null
    for (let y = c.row; y < c.row + c.rowSpan; y++) {
      for (let x = c.col; x < c.col + c.colSpan; x++) {
        if (seen.has(`${x},${y}`)) return null
        seen.add(`${x},${y}`)
      }
    }
  }
  if (seen.size !== cols * rows) return null
  const g = { cols, rows, cells }
  return cuts(g) ? g : null
}

/** Another size: what still fits stays, spans cut to the edge, new room empty. */
export function resizeGrid(g: DipGrid, cols: number, rows: number): DipGrid {
  const c = within(cols, g.cols)
  const r = within(rows, g.rows)
  const cells = g.cells
    .filter(x => x.col < c && x.row < r)
    .map(x => ({ ...x, colSpan: Math.min(x.colSpan, c - x.col), rowSpan: Math.min(x.rowSpan, r - x.row) }))
  const next = { cols: c, rows: r, cells }
  for (let row = 0; row < r; row++) {
    for (let col = 0; col < c; col++) if (cellAt(next, col, row) < 0) cells.push({ pane: '', col, row, colSpan: 1, rowSpan: 1 })
  }
  return { ...next, cells: order(cells) }
}

function merged(g: DipGrid, idx: number, right: boolean): DipGrid | null {
  const cell = g.cells[idx]
  if (!cell) return null
  const at = right ? cellAt(g, cell.col + cell.colSpan, cell.row) : cellAt(g, cell.col, cell.row + cell.rowSpan)
  const other = g.cells[at]
  if (!other) return null
  const fits = right
    ? other.col === cell.col + cell.colSpan && other.row === cell.row && other.rowSpan === cell.rowSpan
    : other.row === cell.row + cell.rowSpan && other.col === cell.col && other.colSpan === cell.colSpan
  if (!fits) return null
  const next = copy(g)
  const grown = next.cells[idx]!
  if (right) grown.colSpan += other.colSpan
  else grown.rowSpan += other.rowSpan
  // A merge keeps what the cell held; an empty cell takes its neighbour's.
  grown.pane ||= other.pane
  next.cells.splice(at, 1)
  return cuts(next) ? next : null
}

export const canMergeRight = (g: DipGrid, idx: number) => merged(g, idx, true) !== null
export const canMergeDown = (g: DipGrid, idx: number) => merged(g, idx, false) !== null
export const canSplit = (g: DipGrid, idx: number) => !!g.cells[idx] && (g.cells[idx]!.colSpan > 1 || g.cells[idx]!.rowSpan > 1)

/** The grid merged, and the merged cell's index (the selection follows it). */
export function merge(g: DipGrid, idx: number, right: boolean): { grid: DipGrid; cell: number } {
  const next = merged(g, idx, right)
  if (!next) return { grid: g, cell: idx }
  const { col, row } = g.cells[idx]!
  return { grid: next, cell: cellAt(next, col, row) }
}

/** A merged cell back into single ones, what it held on the top-left. */
export function splitCell(g: DipGrid, idx: number): DipGrid {
  if (!canSplit(g, idx)) return g
  const cell = g.cells[idx]!
  const pieces: DipCell[] = []
  for (let row = cell.row; row < cell.row + cell.rowSpan; row++) {
    for (let col = cell.col; col < cell.col + cell.colSpan; col++) {
      pieces.push({ pane: row === cell.row && col === cell.col ? cell.pane : '', col, row, colSpan: 1, rowSpan: 1 })
    }
  }
  const next = copy(g)
  next.cells.splice(idx, 1, ...pieces)
  return next
}

/** What fills a cell; a pane placed elsewhere moves here, as there is one of each. */
export function assign(g: DipGrid, idx: number, pane: DipCellPane): DipGrid {
  const next = copy(g)
  next.cells.forEach((c, i) => {
    if (i === idx) c.pane = pane
    else if (pane && c.pane === pane) c.pane = ''
  })
  return next
}
