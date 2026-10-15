// library.mjs — what the workspace editor may save, checked on the server
// before anything is written: workspaces (name, folder, model, effort, grid,
// cells) and
// favourites (name, web address, keep in panel). Pure: the mod's tests load it as the
// server does. A workspace is { slug, file }; a favourite { id, name, url }.

import { MAX_GRID } from "./grid.mjs"

const PANELS = ["browser", "files", "changes", "terminal"]

export function slugOf(name, fallback = "workspace") {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || fallback
}

function free(base, taken) {
  let s = base
  for (let i = 2; taken.includes(s); i++) s = `${base}-${i}`
  return s
}

/** A page's address as typed (`gmail.com` is https), or null when it is not one. */
export function urlOf(raw) {
  const text = String(raw ?? "").trim()
  if (!text || /\s/.test(text)) return null
  const url = /^[a-z][a-z0-9+.-]*:/i.test(text) ? text : `https://${text}`
  try {
    const parsed = new URL(url)
    return parsed.protocol.startsWith("http") && parsed.host ? url : null
  } catch {
    return null
  }
}

const isWhole = (v, min, max) => Number.isInteger(v) && v >= min && v <= max
const even = n => Array.from({ length: n }, () => 1 / n)

function sizes(v, n) {
  if (!Array.isArray(v) || v.length !== n || !v.every(x => typeof x === "number" && x > 0)) return even(n)
  const sum = v.reduce((a, b) => a + b, 0)
  return v.map(x => x / sum)
}

function nameError(name, taken, what) {
  if (!name) return `${what} name is required.`
  if (name.length > 60) return "Keep the name under 60 characters."
  if (taken.some(t => t.trim().toLowerCase() === name.toLowerCase())) return `A ${what.toLowerCase()} named "${name}" already exists.`
  return null
}

function cellsError(cells, cols, rows, favorites) {
  if (!Array.isArray(cells) || cells.length === 0) return "Assign at least one panel to the grid."
  const taken = new Set()
  const shown = new Set()
  for (const c of cells) {
    if (!c || !PANELS.includes(c.panel)) return "A cell shows something Workspaces does not know."
    const cs = c.col_span ?? 1
    const rs = c.row_span ?? 1
    if (!isWhole(c.col, 0, cols - 1) || !isWhole(c.row, 0, rows - 1) || !isWhole(cs, 1, cols - c.col) || !isWhole(rs, 1, rows - c.row)) {
      return "A cell lies outside the grid."
    }
    for (let r = c.row; r < c.row + rs; r++) {
      for (let k = c.col; k < c.col + cs; k++) {
        if (taken.has(`${k},${r}`)) return "Two cells overlap."
        taken.add(`${k},${r}`)
      }
    }
    if (c.panel !== "browser") continue
    const fav = favorites.find(f => f.id === c.favorite)
    if (!fav) return "A cell shows a favourite that no longer exists: pick another."
    if (shown.has(fav.id)) return `${fav.name} is in this workspace twice: a page can be shown once.`
    shown.add(fav.id)
  }
  return null
}

const cleanCell = c => ({
  panel: c.panel,
  col: c.col,
  row: c.row,
  ...((c.col_span ?? 1) > 1 ? { col_span: c.col_span } : {}),
  ...((c.row_span ?? 1) > 1 ? { row_span: c.row_span } : {}),
  ...(c.panel === "browser" ? { favorite: c.favorite } : {}),
})

/** A workspace from the editor, checked: the file to write, where, and the
 *  old file a rename leaves behind; or the reason it cannot be saved. */
export function checkWorkspace(input, { workspaces, favorites, choices = { models: [], efforts: [] } }) {
  const original = typeof input?.original === "string" ? input.original : null
  const was = original === null ? null : workspaces.find(w => w.file.name === original)
  if (original !== null && !was) return { error: `There is no workspace "${original}".` }
  const name = String(input?.name ?? "").trim()
  const bad = nameError(name, workspaces.filter(w => w !== was).map(w => w.file.name), "Workspace")
  if (bad) return { error: bad }
  const folder = String(input?.folder ?? "").trim()
  if (folder && !folder.startsWith("/")) return { error: "The folder must be an absolute path, or blank." }
  const model = String(input?.model ?? "").trim()
  if (model && !choices.models.includes(model)) return { error: `"${model}" is not one of the models this session offers.` }
  const effort = String(input?.effort ?? "").trim()
  if (effort && !choices.efforts.includes(effort)) return { error: `"${effort}" is not an effort level.` }
  const { cols, rows } = input ?? {}
  if (!isWhole(cols, 1, MAX_GRID) || !isWhole(rows, 1, MAX_GRID)) return { error: `A grid is 1 to ${MAX_GRID} columns and rows.` }
  const cellsBad = cellsError(input.cells, cols, rows, favorites)
  if (cellsBad) return { error: cellsBad }
  const file = {
    name,
    folder: folder || null,
    model: model || null,
    effort: effort || null,
    cols,
    rows,
    col_widths: sizes(input.col_widths, cols),
    row_heights: sizes(input.row_heights, rows),
    cells: input.cells.map(cleanCell),
  }
  const others = workspaces.filter(w => w !== was).map(w => w.slug)
  const slug = was && slugOf(name) === was.slug ? was.slug : free(slugOf(name), others)
  return { file, slug, replaces: was && was.slug !== slug ? was.slug : null }
}

export function checkWorkspaceDelete(name, workspaces) {
  const w = workspaces.find(x => x.file.name === name)
  return w ? { slug: w.slug } : { error: `There is no workspace "${name}".` }
}

/** A favourite from the editor, checked: the favourites with it saved. */
export function checkFavorite(input, favorites) {
  const id = typeof input?.id === "string" ? input.id : null
  if (id !== null && !favorites.some(f => f.id === id)) return { error: "That favourite no longer exists." }
  const name = String(input?.name ?? "").trim()
  const bad = nameError(name, favorites.filter(f => f.id !== id).map(f => f.name), "Favourite")
  if (bad) return { error: bad }
  const url = urlOf(input?.url)
  if (!url) return { error: `"${String(input?.url ?? "").trim()}" is not a web address.` }
  const keep_in_panel = input?.keep_in_panel === true
  if (id !== null) return { id, favorites: favorites.map(f => (f.id === id ? { ...f, name, url, keep_in_panel } : f)) }
  const fresh = free(slugOf(name, "page"), favorites.map(f => f.id))
  return { id: fresh, favorites: [...favorites, { id: fresh, name, url, keep_in_panel }] }
}

/** The workspaces showing a favourite, by name. */
export const usedBy = (id, workspaces) => workspaces.filter(w => w.file.cells.some(c => c.favorite === id)).map(w => w.file.name)

/** The favourites without one, or why it stays: workspaces still show it. */
export function checkFavoriteDelete(id, favorites, workspaces) {
  const fav = favorites.find(f => f.id === id)
  if (!fav) return { error: "That favourite no longer exists." }
  const users = usedBy(id, workspaces)
  if (users.length) {
    const one = users.length === 1
    return { error: `${users.join(", ")} ${one ? "still shows" : "still show"} ${fav.name}: take it out of ${one ? "that workspace" : "those workspaces"} first.` }
  }
  return { favorites: favorites.filter(f => f.id !== id) }
}

/** What the macOS folder chooser answered: the folder's POSIX path (no
 *  trailing slash), or null when it was cancelled or failed. */
export function pickedFolder({ code, stdout }) {
  const path = String(stdout ?? "").trim()
  if (code !== 0 || !path.startsWith("/")) return null
  return path.length > 1 ? path.replace(/\/+$/, "") : path
}
