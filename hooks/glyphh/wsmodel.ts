// A workspace file and the grid's layout, one from the other. The file is the
// source of truth; the layout is what the grid, /dip and /stream draw from.
import type { Cell, Layout, WorkspaceCell, WorkspaceFile, WorkspaceTab } from '../../types'

export const PERMISSION_MODES = ['default', 'acceptEdits', 'plan', 'auto', 'bypassPermissions'] as const
export const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max'] as const

export function slugOf(name: string): string {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  return slug || 'workspace'
}

function tabFor(url: string): WorkspaceTab {
  let name = url
  try {
    name = new URL(url).host.replace(/^www\./, '')
  } catch {
    // not a URL: its text names it
  }
  return { url, name, no_redirect: false, rpa: { commands: [], sequences: [] } }
}

/** A new file from a layout (the migration, and a new workspace's grid). */
export function fileFromLayout(layout: Layout): WorkspaceFile {
  const tabs: WorkspaceTab[] = []
  const cells = layout.cells.map((c): WorkspaceCell => {
    const cell: WorkspaceCell = { panel: c.panel, col: c.col, row: c.row }
    if (c.rowSpan) cell.row_span = c.rowSpan
    if (c.path) cell.path = c.path
    if (c.panel === 'browser') {
      cell.tab = tabs.length
      tabs.push(tabFor(c.url ?? 'about:blank'))
    }
    return cell
  })
  return {
    name: layout.name,
    model: null,
    folder: layout.desktop?.folder ?? null,
    permission_mode: null,
    effort: null,
    cols: layout.cols,
    rows: layout.rows,
    col_widths: [...layout.colWidths],
    row_heights: [...layout.rowHeights],
    desktop_panes: [...(layout.desktop?.panes ?? [])],
    collapse_sidebar: layout.desktop?.collapseSidebar === true,
    cells,
    tabs,
  }
}

const nums = (v: unknown, n: number): number[] =>
  Array.isArray(v) && v.length === n && v.every(x => typeof x === 'number') ? (v as number[]) : Array(n).fill(1 / n)

/** The layout a file draws; anything missing or malformed takes a default. */
export function layoutFromFile(file: Partial<WorkspaceFile> & { name: string }): Layout {
  const cols = Math.max(1, Math.floor(Number(file.cols) || 1))
  const rows = Math.max(1, Math.floor(Number(file.rows) || 1))
  const tabs = Array.isArray(file.tabs) ? file.tabs : []
  const cells = (Array.isArray(file.cells) ? file.cells : []).map((c): Cell => {
    const cell: Cell = { panel: c.panel, col: c.col, row: c.row }
    if (c.row_span) cell.rowSpan = c.row_span
    if (c.path) cell.path = c.path
    if (c.panel === 'browser') cell.url = tabs[c.tab ?? -1]?.url ?? 'about:blank'
    return cell
  })
  const layout: Layout = { name: file.name, cols, rows, colWidths: nums(file.col_widths, cols), rowHeights: nums(file.row_heights, rows), cells }
  const panes = Array.isArray(file.desktop_panes) ? file.desktop_panes : []
  if (panes.length || file.folder || file.collapse_sidebar) {
    layout.desktop = { panes, collapseSidebar: file.collapse_sidebar === true, folder: file.folder ?? undefined }
  }
  return layout
}

/** A new, empty workspace: one browser cell on a blank tab. */
export function blankFile(name: string): WorkspaceFile {
  return fileFromLayout({
    name,
    cols: 1,
    rows: 1,
    colWidths: [1],
    rowHeights: [1],
    cells: [{ panel: 'browser', col: 0, row: 0, url: 'about:blank' }],
  })
}
