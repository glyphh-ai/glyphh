// grid.mjs — the workspace editor's grid builder, ported from the Glyphh
// app's layouts.ts (v1.6.2): a grid of cells, each 1×1 or merged; Cols/Rows
// resize it in place; → Merge and ↓ Merge join a cell with its neighbour when
// their edges line up; Split breaks a merged cell back into 1×1 cells, the
// top-left one keeping what it showed. Pure and immutable: every change
// returns a new builder. A cell's `content` is "" (empty), an app pane
// ("files", "changes", "terminal"), or "fav:<id>" (a favourite's page).

/** Grids go up to 25×25, as the app's do. */
export const MAX_GRID = 25

const cell = (col, row, content = "") => ({ content, col, row, colSpan: 1, rowSpan: 1 })

/** A fresh grid of empty 1×1 cells, nothing selected. */
export function initCells(cols, rows) {
  const cells = []
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) cells.push(cell(c, r))
  return { cols, rows, cells, selected: -1 }
}

/** The index of the cell covering col,row, or -1. */
export function cellAt(cells, col, row) {
  return cells.findIndex(c => col >= c.col && col < c.col + c.colSpan && row >= c.row && row < c.row + c.rowSpan)
}

/** A workspace file opened in the builder: its cells laid on a fresh grid,
 *  and the 1×1 cells a merged cell covers taken out. */
export function fromFile(file) {
  const b = initCells(file.cols || 2, file.rows || 1)
  for (const s of file.cells) {
    const at = b.cells.find(c => c.col === s.col && c.row === s.row)
    if (!at) continue
    at.content = s.panel === "browser" ? `fav:${s.favorite}` : s.panel
    at.colSpan = s.col_span ?? 1
    at.rowSpan = s.row_span ?? 1
  }
  b.cells = b.cells.filter(c => !b.cells.some(o => o !== c && c.col >= o.col && c.col < o.col + o.colSpan && c.row >= o.row && c.row < o.row + o.rowSpan))
  return b
}

/** Cols/Rows changed in place: cells whose corner still fits stay, spans
 *  cut to the new edges; positions newly in the grid arrive empty. */
export function resize(b, cols, rows) {
  const kept = b.cells
    .filter(c => c.col < cols && c.row < rows)
    .map(c => ({ ...c, colSpan: Math.min(c.colSpan, cols - c.col), rowSpan: Math.min(c.rowSpan, rows - c.row) }))
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) if (cellAt(kept, c, r) === -1) kept.push(cell(c, r))
  return { cols, rows, cells: kept, selected: -1 }
}

export const select = (b, index) => ({ ...b, selected: index })

/** Whether the cell can join the one to its right: same top, same height. */
export function canMergeRight(b, index) {
  const c = b.cells[index]
  if (!c || c.col + c.colSpan >= b.cols) return false
  const right = b.cells[cellAt(b.cells, c.col + c.colSpan, c.row)]
  return !!right && right.col === c.col + c.colSpan && right.row === c.row && right.rowSpan === c.rowSpan
}

/** Whether the cell can join the one below it: same left edge, same width. */
export function canMergeDown(b, index) {
  const c = b.cells[index]
  if (!c || c.row + c.rowSpan >= b.rows) return false
  const below = b.cells[cellAt(b.cells, c.col, c.row + c.rowSpan)]
  return !!below && below.row === c.row + c.rowSpan && below.col === c.col && below.colSpan === c.colSpan
}

export const canSplit = (b, index) => !!b.cells[index] && (b.cells[index].colSpan > 1 || b.cells[index].rowSpan > 1)

function merge(b, index, other, grow) {
  const cells = b.cells.map(c => ({ ...c }))
  const keep = cells[index]
  Object.assign(keep, grow(keep, cells[other]))
  cells.splice(other, 1)
  return { ...b, cells, selected: cells.indexOf(keep) }
}

export function mergeRight(b, index) {
  if (!canMergeRight(b, index)) return b
  const c = b.cells[index]
  return merge(b, index, cellAt(b.cells, c.col + c.colSpan, c.row), (k, o) => ({ colSpan: k.colSpan + o.colSpan }))
}

export function mergeDown(b, index) {
  if (!canMergeDown(b, index)) return b
  const c = b.cells[index]
  return merge(b, index, cellAt(b.cells, c.col, c.row + c.rowSpan), (k, o) => ({ rowSpan: k.rowSpan + o.rowSpan }))
}

/** A merged cell back to 1×1 cells; the top-left keeps the content. */
export function split(b, index) {
  if (!canSplit(b, index)) return b
  const c = b.cells[index]
  const parts = []
  for (let r = c.row; r < c.row + c.rowSpan; r++) {
    for (let k = c.col; k < c.col + c.colSpan; k++) parts.push(cell(k, r, r === c.row && k === c.col ? c.content : ""))
  }
  const cells = [...b.cells]
  cells.splice(index, 1, ...parts)
  return { ...b, cells, selected: -1 }
}

/** The cell at `index` shows `content`. */
export function assign(b, index, content) {
  return { ...b, cells: b.cells.map((c, i) => (i === index ? { ...c, content } : c)) }
}

/** The builder's cells as a workspace file keeps them: the assigned ones. */
export function fileCells(b) {
  return b.cells
    .filter(c => c.content)
    .map(c => ({
      panel: c.content.startsWith("fav:") ? "browser" : c.content,
      col: c.col,
      row: c.row,
      ...(c.colSpan > 1 ? { col_span: c.colSpan } : {}),
      ...(c.rowSpan > 1 ? { row_span: c.rowSpan } : {}),
      ...(c.content.startsWith("fav:") ? { favorite: c.content.slice(4) } : {}),
    }))
}
