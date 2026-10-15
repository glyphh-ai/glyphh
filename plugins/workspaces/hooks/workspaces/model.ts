// A workspace file and its grid: names, addresses, the grid a file without
// one gets, and a file read from disk made whole (earlier versions included).
import type { FileCell, Panel, WorkspaceFile } from '../../types'

/** The app panes a cell can point at, as the pane lists them. */
const PANE_PANELS = ['files', 'changes', 'terminal'] as const satisfies readonly Panel[]

/** Grids go up to 25×25, as the layout page's editor makes them. */
export const MAX_GRID = 25

/** /effort's levels, as it lists them ("Usage: /effort <low|medium|high|xhigh|max|auto|…>");
 *  no /config row holds the effort, so the list is not read at run time. */
export const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max', 'auto']

/** Earlier versions' cell kinds, as this one reads them; null drops the cell. */
const LEGACY_PANELS: Record<string, Panel | null> = {
  browser: 'browser',
  files: 'files',
  tree: 'files',
  file: 'files',
  editor: 'files',
  changes: 'changes',
  diff: 'changes',
  terminal: 'terminal',
  claude: null,
}

export function slugOf(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'workspace'
}

/** A page's address as typed (`gmail.com` is https), or null when it is not one. */
export function urlOf(raw: string): string | null {
  const text = raw.trim()
  if (!text || /\s/.test(text)) return null
  const url = /^[a-z][a-z0-9+.-]*:/i.test(text) ? text : `https://${text}`
  try {
    const parsed = new URL(url)
    return parsed.protocol.startsWith('http') && parsed.host ? url : null
  } catch {
    return null
  }
}

export const evenSizes = (n: number) => Array.from({ length: n }, () => 1 / n)

type Content = Pick<FileCell, 'panel' | 'favorite'>
type Grid = Pick<WorkspaceFile, 'cols' | 'rows' | 'col_widths' | 'row_heights' | 'cells'>

/** The grid for contents that have none: as square as it goes, filled by
 *  column, the first columns holding fewer cells, which grow taller. */
export function defaultGrid(items: Content[]): Grid {
  const n = items.length
  if (n === 0) return { cols: 1, rows: 1, col_widths: [1], row_heights: [1], cells: [] }
  const cols = Math.ceil(Math.sqrt(n))
  const rows = Math.ceil(n / cols)
  const cells: FileCell[] = []
  let next = 0
  for (let col = 0; col < cols; col++) {
    const count = Math.floor(n / cols) + (col >= cols - (n % cols) && n % cols !== 0 ? 1 : 0)
    let row = 0
    for (let i = 0; i < count; i++) {
      const span = i === count - 1 ? rows - row : Math.floor(rows / count)
      cells.push({ ...items[next++]!, col, row, ...(span > 1 ? { row_span: span } : {}) })
      row += span
    }
  }
  return { cols, rows, col_widths: evenSizes(cols), row_heights: evenSizes(rows), cells }
}

/** The slots a cell covers, as "col,row". */
function slotsOf(c: FileCell): string[] {
  const out: string[] = []
  for (let r = c.row; r < c.row + (c.row_span ?? 1); r++) for (let k = c.col; k < c.col + (c.col_span ?? 1); k++) out.push(`${k},${r}`)
  return out
}

/** Cells that fit the grid, spans cut to it, none on top of another. */
export function fitCells(cells: FileCell[], cols: number, rows: number): FileCell[] {
  const taken = new Set<string>()
  const out: FileCell[] = []
  for (const c of cells) {
    if (c.col < 0 || c.col >= cols || c.row < 0 || c.row >= rows) continue
    const span = Math.max(1, Math.min(rows - c.row, c.row_span ?? 1))
    const wide = Math.max(1, Math.min(cols - c.col, c.col_span ?? 1))
    const cell: FileCell = { ...c }
    if (span > 1) cell.row_span = span
    else delete cell.row_span
    if (wide > 1) cell.col_span = wide
    else delete cell.col_span
    const slots = slotsOf(cell)
    if (slots.some(s => taken.has(s))) continue
    for (const s of slots) taken.add(s)
    out.push(cell)
  }
  return out
}

const text = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null)
const whole = (v: unknown, max: number): number | null =>
  typeof v === 'number' && Number.isInteger(v) && v >= 1 && v <= max ? v : null

/** Fractions that sum to 1, or an even split when they are not `n` sizes. */
export function sizesOf(v: unknown, n: number): number[] {
  if (!Array.isArray(v) || v.length !== n || !v.every(x => typeof x === 'number' && x > 0)) return evenSizes(n)
  const sum = (v as number[]).reduce((a, b) => a + b, 0)
  return (v as number[]).map(x => x / sum)
}

/** A page of an earlier version's `tabs`, made a favourite: its id. */
export type TabToFavorite = (tab: { url: string; name: string }) => string

function tabsOf(v: unknown): ({ url: string; name: string } | null)[] {
  if (!Array.isArray(v)) return []
  return v.map((t: unknown) => {
    const url = text((t as { url?: unknown } | null)?.url)
    return url ? { url, name: text((t as { name?: unknown }).name) ?? url } : null
  })
}

function cellOf(raw: unknown, tabs: ({ url: string; name: string } | null)[], toFavorite: TabToFavorite): FileCell | null {
  const c = raw as Record<string, unknown> | null
  const panel = LEGACY_PANELS[String(c?.panel)]
  if (!c || !panel || typeof c.col !== 'number' || typeof c.row !== 'number') return null
  const cell: FileCell = { panel, col: c.col, row: c.row }
  if (typeof c.col_span === 'number') cell.col_span = c.col_span
  if (typeof c.row_span === 'number') cell.row_span = c.row_span
  if (panel !== 'browser') return cell
  const tab = typeof c.tab === 'number' ? tabs[c.tab] : null
  const favorite = text(c.favorite) ?? (tab ? toFavorite(tab) : null)
  return favorite ? { ...cell, favorite } : null
}

/** Cells with each favourite once: one live page cannot be in two cells. */
export function onceEach(cells: FileCell[]): FileCell[] {
  const seen = new Set<string>()
  return cells.filter(c => !c.favorite || (!seen.has(c.favorite) && Boolean(seen.add(c.favorite))))
}

/** A file as read, made whole. An earlier version's file (pages kept as
 *  `tabs`, or no grid) is read too, its pages made favourites by
 *  `toFavorite`; `isLegacy` says it should be written again. */
export function normalise(raw: unknown, toFavorite: TabToFavorite): { file: WorkspaceFile; isLegacy: boolean } | null {
  if (!raw || typeof raw !== 'object') return null
  const f = raw as Record<string, unknown>
  const name = text(f.name)
  if (!name) return null
  const tabs = tabsOf(f.tabs)
  const cols = whole(f.cols, MAX_GRID)
  const rows = whole(f.rows, MAX_GRID)
  let grid: Grid
  if (cols && rows && Array.isArray(f.cells)) {
    const cells = f.cells.flatMap(c => cellOf(c, tabs, toFavorite) ?? [])
    grid = { cols, rows, col_widths: sizesOf(f.col_widths, cols), row_heights: sizesOf(f.row_heights, rows), cells: onceEach(fitCells(cells, cols, rows)) }
  } else {
    const panes = Array.isArray(f.desktop_panes) ? f.desktop_panes.map(p => LEGACY_PANELS[String(p)]) : []
    const items: Content[] = [
      ...tabs.flatMap(t => (t ? [{ panel: 'browser' as const, favorite: toFavorite(t) }] : [])),
      ...PANE_PANELS.filter(p => panes.includes(p)).map(panel => ({ panel })),
    ]
    grid = defaultGrid(onceEach(items as FileCell[]))
  }
  const isLegacy = f.tabs !== undefined || !Array.isArray(f.cells)
  return { file: { name, folder: text(f.folder), model: text(f.model), effort: text(f.effort), ...grid }, isLegacy }
}
