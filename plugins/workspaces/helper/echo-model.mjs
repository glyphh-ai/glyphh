// echo-model.mjs — the layout page's home, as data: the Echo wall (pages of
// tiles, folders), the dock, the cards' flow and grid geometry, and the wall
// state kept across sessions. Ported from the Glyphh app (code-workbench.ts,
// help/dock-items.ts, dock-band.ts, wall-swipe.ts at v1.6.2) without its
// agent, composer or IPC. Pure: the page imports it, and so do the mod's tests.
//
// Keys: a favourite's tile is `fav:<id>`, a workspace's `layout:<name>`, a
// folder's `folder:<id>`; the dock's own items are `closeall`, `workspaces`
// and `newfav`.

/** The dock's own items, in their default order. */
export const DOCK_ITEMS = Object.freeze([
  { key: "closeall", title: "Close all" },
  { key: "workspaces", title: "Workspaces" },
  { key: "newfav", title: "New favourite" },
])
export const DEFAULT_DOCK = DOCK_ITEMS.map(d => d.key)
export const dockItemFor = key => DOCK_ITEMS.find(d => d.key === key) ?? null

/** The wall's tiles from the library: every favourite, then every workspace. */
export function tilesFrom({ workspaces, favorites }) {
  const fav = id => favorites.find(f => f.id === id)
  return [
    ...favorites.map(f => ({ key: `fav:${f.id}`, kind: "fav", name: f.name, url: f.url, fav: f.id })),
    ...workspaces.map(({ file }) => ({
      key: `layout:${file.name}`,
      kind: "layout",
      name: file.name,
      cells: file.cells.slice(0, 4).map(c => (c.panel === "browser" ? { url: fav(c.favorite)?.url ?? "", name: fav(c.favorite)?.name ?? "?" } : { panel: c.panel, name: c.panel })),
    })),
  ]
}

/**
 * The wall's list, in order, no duplicates (dock-items.ts wallTilesFor):
 * dock ON → the wall's tiles minus whatever the dock carries; dock OFF → the
 * dock's tiles first, in its order, then the wall's.
 */
export function wallTilesFor({ dockEnabled, dockItems, wallItems, keyOf }) {
  const out = []
  const seen = new Set()
  const take = t => {
    const k = keyOf(t)
    if (k !== null) {
      if (seen.has(k)) return
      seen.add(k)
    }
    out.push(t)
  }
  if (dockEnabled) for (const t of dockItems) seen.add(keyOf(t))
  else for (const t of dockItems) take(t)
  for (const t of wallItems) take(t)
  return out
}

/** The dock's keys kept when the library is re-read: a tile that left (a
 *  deleted favourite or workspace) goes; the dock's own items stay. */
export function keepDockKeys(keys, tiles) {
  const live = new Set(tiles.map(t => t.key))
  return keys.filter(k => dockItemFor(k) || live.has(k) || k.startsWith("folder:"))
}

/** The wall in order: the kept order first, new tiles after; tiles in a
 *  folder are off the wall, the folder stands where the order puts it. */
export function orderWall(tiles, { order = [], folders = [] } = {}) {
  const inFolders = new Set(folders.flatMap(f => f.keys))
  const byKey = new Map(tiles.map(t => [t.key, t]))
  for (const f of folders) byKey.set(`folder:${f.id}`, folderTile(f, tiles))
  const out = []
  const used = new Set()
  for (const k of order) {
    const t = byKey.get(k)
    if (!t || used.has(k) || inFolders.has(k)) continue
    used.add(k)
    out.push(t)
  }
  for (const [k, t] of byKey) if (!used.has(k) && !inFolders.has(k)) out.push(t)
  return out
}

/** A folder's tile: its name, and the first four members' minis. */
export function folderTile(folder, tiles) {
  const byKey = new Map(tiles.map(t => [t.key, t]))
  return {
    key: `folder:${folder.id}`,
    kind: "folder",
    name: folder.name,
    folder: folder.id,
    cells: folder.keys.slice(0, 4).map(k => byKey.get(k)).filter(Boolean).map(t => ({ url: t.url ?? "", name: t.name })),
  }
}

/** The wall cut into pages of `perPage`; always at least one. */
export function pagesOf(list, perPage) {
  const pages = []
  for (let i = 0; i < list.length; i += perPage) pages.push(list.slice(i, i + perPage))
  return pages.length ? pages : [[]]
}

/** `key` moved to stand before `before` (null: the end). */
export function moveKey(order, key, before) {
  const rest = order.filter(k => k !== key)
  const at = before === null ? -1 : rest.indexOf(before)
  rest.splice(at < 0 ? rest.length : at, 0, key)
  return rest
}

// ── Folders ──────────────────────────────────────────────────────────────────

/** A new folder holding `onto` and `key`, where `onto` stood. */
export function createFolder(state, key, onto, id) {
  if (key === onto || key.startsWith("folder:") || onto.startsWith("folder:")) return state
  const folders = [...state.folders, { id, name: "Folder", keys: [onto, key] }]
  const order = state.order.map(k => (k === onto ? `folder:${id}` : k)).filter(k => k !== key)
  if (!order.includes(`folder:${id}`)) order.push(`folder:${id}`)
  return { ...state, folders, order }
}

export function addToFolder(state, key, folderId) {
  const f = state.folders.find(x => x.id === folderId)
  if (!f || key.startsWith("folder:") || f.keys.includes(key)) return state
  return {
    ...state,
    folders: state.folders.map(x => (x.id === folderId ? { ...x, keys: [...x.keys, key] } : x)),
    order: state.order.filter(k => k !== key),
  }
}

/** A tile taken out of its folder, back on the wall after it; an emptied folder goes. */
export function removeFromFolder(state, key, folderId) {
  const f = state.folders.find(x => x.id === folderId)
  if (!f || !f.keys.includes(key)) return state
  const keys = f.keys.filter(k => k !== key)
  const folders = keys.length ? state.folders.map(x => (x.id === folderId ? { ...x, keys } : x)) : state.folders.filter(x => x.id !== folderId)
  const at = state.order.indexOf(`folder:${folderId}`)
  const order = state.order.filter(k => k !== key && (keys.length || k !== `folder:${folderId}`))
  order.splice(at < 0 ? order.length : keys.length ? at + 1 : at, 0, key)
  return { ...state, folders, order }
}

export function renameFolder(state, folderId, name) {
  const n = String(name).trim().slice(0, 60)
  return n ? { ...state, folders: state.folders.map(x => (x.id === folderId ? { ...x, name: n } : x)) } : state
}

/** Keys of tiles that left the library dropped from folders and order. */
export function pruneEcho(state, tiles) {
  const live = new Set(tiles.map(t => t.key))
  const folders = state.folders.map(f => ({ ...f, keys: f.keys.filter(k => live.has(k)) })).filter(f => f.keys.length)
  const folderKeys = new Set(folders.map(f => `folder:${f.id}`))
  return {
    ...state,
    folders,
    order: state.order.filter(k => live.has(k) || folderKeys.has(k)),
    dock: keepDockKeys(state.dock, tiles),
  }
}

// ── Cards: the flow and the grid (code-workbench.ts flowColumns, flowRects, gridRects) ──

export const GAP = 7

/** Cards fill columns in open order, two to a column, then a new column to
 *  the right; a card driven to a side (solo) keeps its column to itself. */
export function flowColumns(cards) {
  const cols = []
  for (const c of cards) {
    const target = c.solo ? undefined : cols.find(col => col.length < 2 && !col.some(x => x.solo))
    if (target) target.push(c)
    else cols.push([c])
  }
  return cols
}

const norm = a => {
  const t = a.reduce((x, y) => x + y, 0) || 1
  return a.map(v => v / t)
}
const pre = (a, i) => a.slice(0, i).reduce((x, y) => x + y, 0)

/** Seam fractions kept only for the shape they shaped: a new shape starts even. */
export function syncFractions(cols, { colFr = [], rowFr = [] } = {}) {
  return {
    colFr: colFr.length === cols.length ? colFr : cols.map(() => 1),
    rowFr: cols.map((col, i) => (rowFr[i]?.length === col.length ? rowFr[i] : col.map(() => 1))),
  }
}

/** Each card's rect in the band, by id. */
export function flowRects(cards, band, fr) {
  const cols = flowColumns(cards)
  const { colFr, rowFr } = syncFractions(cols, fr)
  const cw = norm(colFr)
  const availW = band.width - GAP * (cols.length - 1)
  const out = new Map()
  let x = band.left
  cols.forEach((col, ci) => {
    const colW = availW * cw[ci]
    const rh = norm(rowFr[ci])
    const availH = band.height - GAP * (col.length - 1)
    let y = band.top
    col.forEach((c, ri) => {
      const h = availH * rh[ri]
      out.set(c.id, { left: x, top: y, width: Math.max(160, colW), height: Math.max(110, h) })
      y += h + GAP
    })
    x += colW + GAP
  })
  return out
}

/** A workspace grid's cells' rects in the band: seams only between cells. */
export function gridRects(grid, band) {
  const cw = norm(grid.colWidths)
  const rh = norm(grid.rowHeights)
  const out = new Map()
  for (const c of grid.cells) {
    const cs = c.colSpan ?? 1
    const rs = c.rowSpan ?? 1
    const left = band.left + pre(cw, c.col) * band.width + (c.col === 0 ? 0 : GAP / 2)
    const right = band.left + pre(cw, c.col + cs) * band.width - (c.col + cs >= cw.length ? 0 : GAP / 2)
    const top = band.top + pre(rh, c.row) * band.height + (c.row === 0 ? 0 : GAP / 2)
    const bottom = band.top + pre(rh, c.row + rs) * band.height - (c.row + rs >= rh.length ? 0 : GAP / 2)
    out.set(c.id, { left, top, width: Math.max(120, right - left), height: Math.max(90, bottom - top) })
  }
  return out
}

/** Where the seams between a grid's columns and rows lie, for dragging them. */
export function gridSeams(grid, band) {
  const cw = norm(grid.colWidths)
  const rh = norm(grid.rowHeights)
  return {
    cols: cw.slice(0, -1).map((_, i) => ({ index: i, x: band.left + pre(cw, i + 1) * band.width })),
    rows: rh.slice(0, -1).map((_, i) => ({ index: i, y: band.top + pre(rh, i + 1) * band.height })),
  }
}

/** Two neighbouring fractions after a seam moved by `shift` (a fraction of the
 *  whole), neither below `min` of the whole. */
export function slideSeam(fractions, index, shift, min = 0.08) {
  const f = norm(fractions)
  const a = f[index]
  const b = f[index + 1]
  if (a === undefined || b === undefined) return f
  const moved = Math.max(min - a, Math.min(b - min, shift))
  const out = [...f]
  out[index] = a + moved
  out[index + 1] = b - moved
  return out
}

/** Opening a favourite: never two copies. Already a card: nothing changes;
 *  a pinned card takes it in place of what it showed; else a new card. */
export function openFavorite(cards, fav, newId) {
  if (cards.some(c => c.fav === fav)) return cards
  const pinned = cards.find(c => c.pinned)
  if (pinned) return cards.map(c => (c === pinned ? { ...c, fav } : c))
  return [...cards, { id: newId, fav, solo: false, pinned: false }]
}

/** A card dragged by its head onto another: the two swap places, and a
 *  place's own column (solo) stays with the place. */
export function swapCards(cards, a, b) {
  const i = cards.findIndex(c => c.id === a)
  const j = cards.findIndex(c => c.id === b)
  if (i < 0 || j < 0 || i === j) return cards
  const out = [...cards]
  out[i] = { ...cards[j], solo: cards[i].solo }
  out[j] = { ...cards[i], solo: cards[j].solo }
  return out
}

/** A grid card dragged onto another: the two cells trade places and spans. */
export function swapCells(grid, a, b) {
  const x = grid.cells.find(c => c.id === a)
  const y = grid.cells.find(c => c.id === b)
  if (!x || !y || x === y) return grid
  const place = c => ({ col: c.col, row: c.row, colSpan: c.colSpan, rowSpan: c.rowSpan })
  return { ...grid, cells: grid.cells.map(c => (c === x ? { ...c, ...place(y) } : c === y ? { ...c, ...place(x) } : c)) }
}

/** A loose favourite opened over a workspace: the grid's pages become loose
 *  cards, in the grid's order, ahead of the cards that waited behind it. */
export function dissolveGrid(grid, cards, newId) {
  let out = []
  for (const c of grid.cells) if (c.fav) out = openFavorite(out, c.fav, newId())
  for (const c of cards) if (!out.some(x => x.fav === c.fav)) out.push(c)
  return out
}

/** A card dropped at the band's edge: its own column, at that side. */
export function soloCard(cards, id, side) {
  const c = cards.find(x => x.id === id)
  if (!c) return cards
  const rest = cards.filter(x => x !== c)
  const moved = { ...c, solo: true }
  return side === "left" ? [moved, ...rest] : [...rest, moved]
}

/** One pinned card at most: pinning one unpins the rest. */
export function pinCard(cards, id) {
  const on = !cards.find(c => c.id === id)?.pinned
  return cards.map(c => ({ ...c, pinned: on && c.id === id }))
}

/** A workspace's grid of cards; the loose cards showing its favourites move
 *  into it (adopt), the rest stay loose behind it. */
export function workspaceGrid(layout, cards) {
  const favs = new Set(layout.cells.filter(c => c.page).map(c => c.page))
  return {
    grid: {
      workspace: layout.name,
      colWidths: layout.colWidths,
      rowHeights: layout.rowHeights,
      cells: layout.cells.map((c, i) => ({ id: `g${i}`, col: c.col, row: c.row, colSpan: c.colSpan ?? 1, rowSpan: c.rowSpan ?? 1, fav: c.page ?? null, panel: c.panel, url: c.url ?? null, title: c.title ?? null, keepInPanel: c.keepInPanel === true })),
    },
    cards: cards.filter(c => !favs.has(c.fav)),
  }
}

// ── The wall's state, kept across sessions (scheduleWallSave, restoreWallOnce) ──

/** What is kept: the workspace on stage, and the loose cards. */
export function serializeWall({ grid, cards }) {
  return { workspace: grid ? grid.workspace : null, cards: cards.map(c => ({ fav: c.fav, solo: c.solo === true, pinned: c.pinned === true })) }
}

/** A kept wall state made whole; anything malformed is an empty wall. */
export function parseWall(raw) {
  const workspace = typeof raw?.workspace === "string" ? raw.workspace : null
  const cards = Array.isArray(raw?.cards)
    ? raw.cards.filter(c => typeof c?.fav === "string").map((c, i) => ({ id: `c${i}`, fav: c.fav, solo: c.solo === true, pinned: c.pinned === true }))
    : []
  return { workspace, cards }
}

/** The echo file's parts (page order, dock order, folders, wall) made whole. */
export function parseEcho(raw) {
  const strings = v => (Array.isArray(v) ? v.filter(k => typeof k === "string") : null)
  const folders = Array.isArray(raw?.folders)
    ? raw.folders.filter(f => typeof f?.id === "string" && typeof f?.name === "string").map(f => ({ id: f.id, name: f.name, keys: strings(f.keys) ?? [] }))
    : []
  return { order: strings(raw?.order) ?? [], dock: strings(raw?.dock) ?? [...DEFAULT_DOCK], folders, wall: parseWall(raw?.wall) }
}

/** Saves that wait for the restore: nothing is written until the kept state
 *  has been put back, or the first paint would write an empty wall over it. */
export function wallSaver({ save, delay = 400, setTimer = setTimeout, clearTimer = clearTimeout }) {
  let restored = false
  let timer = null
  return {
    restored() {
      restored = true
    },
    schedule(state) {
      if (!restored) return false
      if (timer) clearTimer(timer)
      timer = setTimer(() => {
        timer = null
        save(state)
      }, delay)
      return true
    },
  }
}

// ── The dock ─────────────────────────────────────────────────────────────────

/** The dock's magnification (applyDockZoomAt): each item's scale by its
 *  distance from the pointer, a Gaussian of `sigma` px, up to `zoom`. */
export function dockScales(centers, x, zoom = 1.25, sigma = 110) {
  if (x === null || zoom <= 1.001) return centers.map(() => 1)
  return centers.map(c => 1 + (zoom - 1) * Math.exp(-((x - c) ** 2) / (2 * sigma * sigma)))
}

/** Whether the dock tucks away: it auto-hides, and cards cover the wall. */
export const dockTucked = ({ autoHide, cardsUp }) => autoHide && cardsUp

// ── Swipe (wall-swipe.ts) ────────────────────────────────────────────────────

export const SWIPE_WHEEL_PX = 60
export const SWIPE_COOLDOWN_MS = 450
export const WHEEL_GESTURE_GAP_MS = 150

export function swipeStep({ dx, dy, threshold, sinceLast, cooldown = SWIPE_COOLDOWN_MS }) {
  if (sinceLast !== undefined && sinceLast < cooldown) return 0
  const ax = Math.abs(dx)
  if (!(ax >= threshold) || !(ax > Math.abs(dy))) return 0
  return dx > 0 ? 1 : -1
}

export const wheelSwipeState = () => ({ accX: 0, accY: 0, lastEventAt: -Infinity, lastStepAt: -Infinity, armed: true })

/** One wheel event fed to the gesture: the page step it completes (one per gesture). */
export function wheelSwipeFeed(s, deltaX, deltaY, now) {
  const gap = now - s.lastEventAt
  s.lastEventAt = now
  if (gap > WHEEL_GESTURE_GAP_MS) Object.assign(s, { accX: 0, accY: 0, armed: true })
  if (!s.armed) return 0
  s.accX += deltaX
  s.accY += deltaY
  const step = swipeStep({ dx: s.accX, dy: s.accY, threshold: SWIPE_WHEEL_PX, sinceLast: Number.isFinite(s.lastStepAt) ? now - s.lastStepAt : undefined })
  if (step !== 0) Object.assign(s, { armed: false, lastStepAt: now, accX: 0, accY: 0 })
  return step
}

// ── Search ───────────────────────────────────────────────────────────────────

const hit = (t, q) => t.name.toLowerCase().includes(q) || t.key.toLowerCase().includes(q)

/** The keys the search dims, and the tile Enter opens (a name starting with
 *  the query first). */
export function searchWall(tiles, query) {
  const q = query.trim().toLowerCase()
  if (!q) return { dim: new Set(), best: null }
  const pool = tiles.filter(t => hit(t, q))
  return { dim: new Set(tiles.filter(t => !hit(t, q)).map(t => t.key)), best: pool.find(t => t.name.toLowerCase().startsWith(q)) ?? pool[0] ?? null }
}
