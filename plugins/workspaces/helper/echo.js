// echo.js — the layout page's home: the Glyphh app's Echo launcher
// (code-workbench.ts at v1.6.2) without its agent, composer or IPC. The wall:
// pages of tiles (favourites, workspaces as 2×2 minis, folders), dots and
// swipe, a search pill, press-and-hold to edit. The dock: Close all,
// Workspaces, New favourite and any tile dragged in. Cards: a favourite opens
// as a live card in the flow (two to a column); a workspace opens as its grid
// of cards. The data and geometry are echo-model.mjs; the live pictures, the
// input and the headers are the layout page's (window.WORKSPACES).

const W = window.WORKSPACES
const { token: T, api, op, liveView, slotHead, iconButton, ICONS, pageInfo, canvases } = W
const M = await import(`/ws/echo-model.mjs?t=${T}`)

const svg = body => `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
const MARKS = {
  closeall: svg('<rect x="2.5" y="2.5" width="11" height="11" rx="2"/><path d="m6 6 4 4"/><path d="m10 6-4 4"/>'),
  workspaces: svg('<rect x="2.5" y="2.5" width="4.5" height="4.5" rx="1"/><rect x="9" y="2.5" width="4.5" height="4.5" rx="1"/><rect x="2.5" y="9" width="4.5" height="4.5" rx="1"/><rect x="9" y="9" width="4.5" height="4.5" rx="1"/>'),
  newfav: svg('<path d="M8 3v10"/><path d="M3 8h10"/>'),
  search: svg('<circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/>'),
  pin: svg('<path d="M6 2.5h4l-.5 4 2 2v1h-7v-1l2-2z"/><path d="M8 9.5v4"/>'),
}
const PANES = { files: ["Files", "/files"], changes: ["Changes", "/diff"], terminal: ["Terminal", "/term"] }
const HOLD_MS = 520 // press-and-hold into edit mode
const SETTLE_MS = 240 // a card's move (echo.css transition) and a little
const EDGE_PX = 36 // a head dropped this close to the band's side goes solo

// ── State ───────────────────────────────────────────────────────────────────
let settings = { home: "wall", dock: true, dockAutoHide: true, iconsPerPage: 40 }
let lib = { workspaces: [], favorites: [] }
let layouts = []
let active = ""
let echo = { order: [], dock: [...M.DEFAULT_DOCK], folders: [] }
let cards = [] // the loose cards (flow), in open order
let grid = null // the workspace on stage
let gridSource = "" // the layout the grid was built from
let flowFr = {} // the flow's seams
let expanded = null // the card over the whole band
let editing = false
let pageAt = 0
let folderOpen = null
let dragging = false
let settleUntil = 0
let started = false
let seq = 0
const newId = () => `n${++seq}`

const saver = M.wallSaver({ save: s => api("/api/echo", s).catch(() => {}) })
const persist = () => saver.schedule({ ...echo, wall: M.serializeWall({ grid, cards }) })

// ── The page's parts ────────────────────────────────────────────────────────
const el = (tag, className = "", props = {}) => Object.assign(document.createElement(tag), { className }, props)
const root = document.getElementById("echo")
const hot = el("div", "echo-dock-hot")
const dockWrap = el("div", "echo-dock-wrap")
const dock = el("div", "echo-dock")
dockWrap.append(dock)
const stage = el("div", "echo-stage")
const searchWrap = el("div", "echo-search-wrap", { innerHTML: MARKS.search })
const search = el("input", "echo-search", { type: "text", placeholder: "Search", spellcheck: false, autocomplete: "off" })
searchWrap.append(search)
const pages = el("div", "echo-pages")
const dots = el("div", "echo-dots")
stage.append(searchWrap, pages, dots)
const deck = el("div", "", { id: "cards" })
const edge = el("div", "edge-drop")
deck.append(edge)
root.append(stage, deck, hot, dockWrap)

// ── Tiles ───────────────────────────────────────────────────────────────────
function allTiles() {
  const tiles = M.tilesFrom(lib)
  const byKey = new Map([...tiles, ...echo.folders.map(f => M.folderTile(f, tiles))].map(t => [t.key, t]))
  return { tiles, byKey }
}
const navTile = key => ({ key, kind: "nav", name: M.dockItemFor(key).title })
const dockTiles = byKey => echo.dock.map(k => (M.dockItemFor(k) ? navTile(k) : byKey.get(k))).filter(Boolean)
const wallKeys = () => M.orderWall(allTiles().tiles, echo).map(t => t.key)

/** The wall in order: the dock's tiles left off it (dock on) or leading it (off). */
function wallList() {
  const { tiles, byKey } = allTiles()
  return M.wallTilesFor({ dockEnabled: settings.dock, dockItems: dockTiles(byKey), wallItems: M.orderWall(tiles, echo), keyOf: t => t.key })
}

/** A page's icon through the helper (token-checked); its first letter if it has none. */
function favicon(url, name) {
  const letter = () => el("span", "echo-app-fallback", { textContent: (name || "?").trim().charAt(0).toUpperCase() || "?" })
  if (!url) return letter()
  const img = el("img", "", { alt: "", draggable: false, src: `/api/favicon?url=${encodeURIComponent(url)}&t=${T}` })
  img.onerror = () => img.replaceWith(letter())
  return img
}

function tileIcon(t) {
  const ic = el("span", "echo-app-ic")
  if (t.kind === "nav") ic.innerHTML = MARKS[t.key]
  else if (t.kind === "fav") ic.append(favicon(t.url, t.name))
  else {
    const mini = el("span", "echo-mini")
    for (const c of t.cells) {
      const cell = el("span")
      if (c.panel) cell.innerHTML = ICONS[c.panel] ?? ICONS.page
      else cell.append(favicon(c.url, c.name))
      mini.append(cell)
    }
    ic.append(mini)
  }
  return ic
}

function openTile(t) {
  if (t.kind === "folder") return showFolder(t.folder)
  closeFolder()
  if (t.key === "workspaces" && W.editorOpen()) return W.hideEditor()
  W.hideEditor()
  if (t.kind === "fav") return openFav(t.fav)
  if (t.kind === "layout") return openWorkspace(t.name)
  if (t.key === "closeall") return closeAll()
  if (t.key === "workspaces") return W.showEditor("workspaces")
  if (t.key === "newfav") return W.showEditor("new-favorite")
}

/** A tile on the wall, in a folder or in the dock. */
function tileButton(t, where) {
  const inDock = where === "dock"
  const b = el("button", inDock ? "echo-dock-btn" : "echo-app-btn", { type: "button", title: t.name })
  b.dataset.key = t.key
  b.append(tileIcon(t))
  if (inDock) b.dataset.title = t.name
  else b.append(el("span", "echo-app-name", { textContent: t.name }))
  if (where === "wall" && t.kind !== "nav") {
    const del = el("span", "echo-app-del", { title: t.kind === "folder" ? "Ungroup" : "Delete", innerHTML: ICONS.close })
    del.onclick = e => {
      e.stopPropagation()
      removeTile(t)
    }
    b.append(del)
  }
  b.onclick = () => {
    if (b._held) return void (b._held = false)
    if (!editing || t.kind === "folder") openTile(t)
  }
  if (where === "wall") holdToEdit(b)
  draggableTile(b, t, where)
  return b
}

/** Press and hold a wall tile: edit mode (drag to reorder, ✕ to delete). */
function holdToEdit(b) {
  let timer, x, y
  const cancel = () => clearTimeout(timer)
  b.addEventListener("pointerdown", e => {
    if (editing || e.button !== 0) return
    x = e.clientX
    y = e.clientY
    timer = setTimeout(() => {
      b._held = true
      setEditing(true)
    }, HOLD_MS)
  })
  b.addEventListener("pointermove", e => Math.hypot(e.clientX - x, e.clientY - y) > 6 && cancel())
  b.addEventListener("pointerup", cancel)
  b.addEventListener("pointerleave", cancel)
}

function setEditing(on) {
  editing = on
  stage.classList.toggle("echo-edit", on)
  for (const b of pages.querySelectorAll(".echo-app-btn")) b.draggable = on
}

// ── Dragging tiles: reorder, folders, the dock ──────────────────────────────
let dragKey = null
let dragFrom = null // "wall", "dock" or a folder's id
const clearDrops = () => document.querySelectorAll(".drop, .drop-before, .drop-after").forEach(n => n.classList.remove("drop", "drop-before", "drop-after"))

function draggableTile(b, t, where) {
  b.draggable = where !== "wall" || editing
  b.addEventListener("dragstart", e => {
    dragKey = t.key
    dragFrom = where
    e.dataTransfer.effectAllowed = "move"
    e.dataTransfer.setData("text/plain", t.key)
  })
  b.addEventListener("dragend", () => {
    dragKey = dragFrom = null
    clearDrops()
  })
  if (where !== "wall" && where !== "dock") return // a folder's tiles only leave it
  b.addEventListener("dragover", e => {
    if (!dragKey || dragKey === t.key) return
    e.preventDefault()
    e.stopPropagation()
    clearDrops()
    const zone = zoneOf(e, b, t, where)
    b.classList.add(zone === "into" ? "drop" : `drop-${zone}`)
  })
  b.addEventListener("drop", e => {
    if (!dragKey || dragKey === t.key) return
    e.preventDefault()
    e.stopPropagation()
    dropOn(t, zoneOf(e, b, t, where), where)
  })
}

/** Where a drop on a tile lands: into it (a folder), or before or after it. */
function zoneOf(e, b, t, where) {
  const r = b.getBoundingClientRect()
  const f = (e.clientX - r.left) / r.width
  const groups = where === "wall" && t.kind !== "nav" && !dragKey.startsWith("folder:") && !M.dockItemFor(dragKey)
  if (groups && f > 0.25 && f < 0.75) return "into"
  return f < 0.5 ? "before" : "after"
}

/** The dragged tile taken from where it came: its folder, or the dock. */
function lifted(key) {
  let s = { ...echo, order: wallKeys() }
  if (dragFrom && dragFrom !== "wall" && dragFrom !== "dock") s = M.removeFromFolder(s, key, dragFrom)
  return s
}

function dropOn(t, zone, where) {
  const key = dragKey
  let s = lifted(key)
  if (where === "dock") {
    const keys = s.dock.filter(k => k !== key)
    const at = keys.indexOf(t.key) + (zone === "after" ? 1 : 0)
    keys.splice(at, 0, key)
    s = { ...s, dock: keys }
  } else {
    if (M.dockItemFor(key)) return clearDrops() // the dock's own items stay in it
    s = { ...s, dock: s.dock.filter(k => k !== key) }
    if (zone === "into") s = t.kind === "folder" ? M.addToFolder(s, key, t.folder) : M.createFolder(s, key, t.key, `f${Date.now().toString(36)}`)
    else {
      const order = s.order.filter(k => k !== key)
      const before = zone === "before" ? t.key : (order[order.indexOf(t.key) + 1] ?? null)
      s = { ...s, order: M.moveKey(s.order, key, before) }
    }
  }
  echo = s
  closeFolder()
  persist()
  render()
}

// The dock's empty space takes a tile at its end; the wall's, at the wall's end.
dock.addEventListener("dragover", e => {
  if (!dragKey) return
  e.preventDefault()
  dock.classList.add("drop")
})
dock.addEventListener("dragleave", () => dock.classList.remove("drop"))
dock.addEventListener("drop", e => {
  e.preventDefault()
  dock.classList.remove("drop")
  const key = dragKey
  if (!key || echo.dock.includes(key)) return
  echo = { ...lifted(key), dock: [...echo.dock, key] }
  closeFolder()
  persist()
  render()
})
pages.addEventListener("dragover", e => dragKey && dragFrom !== "wall" && !M.dockItemFor(dragKey) && e.preventDefault())
pages.addEventListener("drop", e => {
  e.preventDefault()
  const key = dragKey
  if (!key || M.dockItemFor(key)) return
  const s = lifted(key)
  echo = { ...s, dock: s.dock.filter(k => k !== key), order: M.moveKey(s.order, key, null) }
  persist()
  render()
})

/** ✕ in edit mode: a folder ungroups; a favourite or a workspace is deleted. */
async function removeTile(t) {
  if (t.kind === "folder") {
    const f = echo.folders.find(x => x.id === t.folder)
    let s = { ...echo, order: wallKeys() }
    for (const k of [...f.keys].reverse()) s = M.removeFromFolder(s, k, f.id)
    echo = s
    persist()
    return render()
  }
  const fav = t.kind === "fav"
  const yes = await W.confirm({
    title: `Delete “${t.name}”?`,
    body: fav ? "The page is no longer kept as a favourite." : "The workspace file is deleted.",
    confirmLabel: fav ? "Delete favourite" : "Delete workspace",
  })
  if (!yes) return
  const r = await api(fav ? "/api/favorite/delete" : "/api/workspace/delete", fav ? { id: t.fav } : { name: t.name }).catch(() => ({ error: "The helper did not answer." }))
  if (r.error) toast(r.error)
}

let toastTimer
function toast(message) {
  document.querySelector(".echo-toast")?.remove()
  const box = el("div", "echo-toast", { textContent: message, role: "status" })
  root.append(box)
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => box.remove(), 5000)
}

// ── Folders ─────────────────────────────────────────────────────────────────
function showFolder(id) {
  const f = echo.folders.find(x => x.id === id)
  if (!f) return
  closeFolder()
  folderOpen = id
  const { byKey } = allTiles()
  const back = el("div", "echo-folder-back")
  const box = el("div", "echo-folder", { role: "dialog", ariaModal: "true" })
  const name = el("input", "", { type: "text", value: f.name, spellcheck: false, ariaLabel: "Folder name" })
  name.onchange = () => {
    echo = M.renameFolder(echo, id, name.value)
    persist()
    render()
  }
  const tiles = el("div", "echo-page-grid")
  tiles.append(...f.keys.map(k => byKey.get(k)).filter(Boolean).map(t => tileButton(t, id)))
  box.append(name, tiles, el("div", "echo-folder-hint", { textContent: "Drag a tile out to put it back on the wall." }))
  back.append(box)
  back.onmousedown = e => e.target === back && closeFolder()
  // Dropped outside the box: out of the folder, onto the wall after it.
  box.addEventListener("dragover", e => e.stopPropagation())
  back.addEventListener("dragover", e => dragKey && dragFrom === id && e.preventDefault())
  back.addEventListener("drop", e => {
    e.preventDefault()
    if (!dragKey || dragFrom !== id) return
    echo = M.removeFromFolder({ ...echo, order: wallKeys() }, dragKey, id)
    closeFolder()
    persist()
    render()
  })
  root.append(back)
  name.focus()
}

function closeFolder() {
  folderOpen = null
  root.querySelector(".echo-folder-back")?.remove()
}

// ── The wall: pages, dots, swipe, search ────────────────────────────────────
function drawWall() {
  const list = wallList()
  const groups = M.pagesOf(list, settings.iconsPerPage)
  pageAt = Math.min(pageAt, groups.length - 1)
  pages.replaceChildren(
    ...groups.map(g => {
      const page = el("div", "echo-page")
      const tiles = el("div", "echo-page-grid")
      tiles.append(...g.map(t => tileButton(t, "wall")))
      page.append(tiles)
      return page
    }),
  )
  drawDots(groups.length)
  stage.classList.toggle("echo-edit", editing)
  applySearch(false)
  requestAnimationFrame(() => (pages.scrollLeft = pageAt * pages.clientWidth))
  if (folderOpen) showFolder(folderOpen)
}

function drawDots(count) {
  dots.replaceChildren(
    ...(count > 1 ? Array.from({ length: count }, (_, i) => el("button", i === pageAt ? "echo-dot active" : "echo-dot", { type: "button", title: `Page ${i + 1}`, onclick: () => goPage(i) })) : []),
  )
}

function goPage(i) {
  const count = pages.children.length
  pageAt = Math.max(0, Math.min(count - 1, i))
  pages.scrollTo({ left: pageAt * pages.clientWidth, behavior: "smooth" })
  drawDots(count)
}

const wheel = M.wheelSwipeState()
pages.addEventListener(
  "wheel",
  e => {
    e.preventDefault()
    const step = M.wheelSwipeFeed(wheel, e.deltaX, e.deltaY, performance.now())
    if (step) goPage(pageAt + step)
  },
  { passive: false },
)
let swipeFrom = null
pages.addEventListener("pointerdown", e => {
  swipeFrom = e.target.closest(".echo-app-btn") && editing ? null : { x: e.clientX, y: e.clientY }
})
pages.addEventListener("pointerup", e => {
  if (!swipeFrom) return
  const step = M.swipeStep({ dx: swipeFrom.x - e.clientX, dy: swipeFrom.y - e.clientY, threshold: 50 })
  swipeFrom = null
  if (step) goPage(pageAt + step)
  else if (editing && !e.target.closest(".echo-app-btn")) setEditing(false)
})

/** The search dims what does not match and turns to the best match's page. */
function applySearch(turn = true) {
  const list = wallList()
  const { dim, best } = M.searchWall(list, search.value)
  for (const b of pages.querySelectorAll(".echo-app-btn")) b.classList.toggle("echo-search-miss", dim.has(b.dataset.key))
  if (turn && best) {
    const i = Math.floor(list.indexOf(best) / settings.iconsPerPage)
    if (i !== pageAt) goPage(i)
  }
}
function clearSearch() {
  search.value = ""
  applySearch(false)
}
search.oninput = () => applySearch()
search.onkeydown = e => {
  if (e.key === "Enter") {
    const { best } = M.searchWall(wallList(), search.value)
    if (best) {
      clearSearch()
      openTile(best)
    }
  } else if (e.key === "Escape") {
    clearSearch()
    search.blur()
  }
}

// ── The dock ────────────────────────────────────────────────────────────────
function drawDock() {
  document.body.classList.toggle("echo-dock-off", !settings.dock)
  dock.replaceChildren(...dockTiles(allTiles().byKey).map(t => tileButton(t, "dock")))
}

/** Magnification: each item grows by its distance from the pointer. */
function zoomDock(x) {
  const items = [...dock.children]
  const left = dock.getBoundingClientRect().left
  const scales = M.dockScales(items.map(b => left + b.offsetLeft + b.offsetWidth / 2), x)
  items.forEach((b, i) => (b.style.transform = scales[i] === 1 ? "" : `scale(${scales[i].toFixed(3)})`))
}
dock.addEventListener("pointermove", e => zoomDock(e.clientX))
dock.addEventListener("pointerleave", () => {
  zoomDock(null)
  setTimeout(() => !dock.matches(":hover") && document.body.classList.remove("echo-dock-peek"), 300)
})
// Tucked away while cards are up: the top edge brings it back.
const peek = () => document.body.classList.add("echo-dock-peek")
hot.addEventListener("pointerenter", peek)
hot.addEventListener("dragenter", peek)

const cardsUp = () => grid !== null || cards.length > 0
function drawTuck() {
  const up = cardsUp()
  document.body.classList.toggle("echo-cards-up", up)
  document.body.classList.toggle("echo-dock-tucked", settings.dock && M.dockTucked({ autoHide: settings.dockAutoHide, cardsUp: up }))
}

// ── Cards ───────────────────────────────────────────────────────────────────
const live = new Map() // a card's key (its favourite, or a pane cell) → its element

/** The band the cards fill: the page, under the dock unless it tucks away. */
function bandRect() {
  const pad = 8
  const dockUp = settings.dock && !document.body.classList.contains("echo-dock-tucked")
  const top = dockUp ? dockWrap.offsetTop + dock.offsetHeight + 12 : pad
  return { left: pad, top, width: innerWidth - pad * 2, height: Math.max(120, innerHeight - top - pad) }
}

/** What each card on stage shows, by key, with its rect. */
function wanted(band) {
  const want = new Map()
  if (grid) {
    const rects = M.gridRects(grid, band)
    for (const c of grid.cells) {
      const fav = lib.favorites.find(f => f.id === c.fav)
      const spec = c.fav ? { page: c.fav, url: c.url ?? fav?.url ?? "", name: fav?.name ?? c.title ?? "", keep: c.keepInPanel || fav?.keep_in_panel === true } : { pane: c.panel }
      want.set(c.fav ?? `pane:${grid.workspace}:${c.id}`, { id: c.id, rect: rects.get(c.id), spec, inGrid: true })
    }
  } else {
    const rects = M.flowRects(cards, band, flowFr)
    for (const c of cards) {
      const fav = lib.favorites.find(f => f.id === c.fav)
      want.set(c.fav, { id: c.id, rect: rects.get(c.id), spec: { page: c.fav, url: fav?.url ?? "", name: fav?.name ?? "", keep: fav?.keep_in_panel === true }, card: c, inGrid: false })
    }
  }
  return want
}

/** Lays the cards out; a card hidden (behind an expanded one, the editor, the
 *  locked screen or a hidden tab) has its page parked, so it sends no frames. */
function layoutCards({ seams = true } = {}) {
  settleUntil = performance.now() + SETTLE_MS
  const band = bandRect()
  const want = wanted(band)
  if (expanded && ![...want.values()].some(w => w.id === expanded)) expanded = null
  for (const [k, e] of live) if (!want.has(k)) retire(k, e)
  const covered = document.hidden || W.editorOpen() || W.licence?.kind === "expired"
  for (const [k, w] of want) {
    const e = live.get(k) ?? makeCard(k, w)
    e._w = w
    drawButtons(e)
    const isExpanded = expanded === w.id
    const hidden = covered || (expanded !== null && !isExpanded)
    const r = isExpanded ? band : w.rect
    e.classList.toggle("expanded", isExpanded)
    Object.assign(e.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px`, display: hidden ? "none" : "" })
    e._show(!hidden)
  }
  if (seams) drawSeams(band, want)
}

function retire(k, e) {
  live.delete(k)
  e._show(false)
  e._stop()
  if (e._id && canvases.get(e._id) === e._canvas) canvases.delete(e._id)
  e.remove()
}

/** A card: its header (favicon, title, buttons), the browser bar, the live page. */
function makeCard(k, w) {
  const e = el("div", "card")
  const { spec } = w
  if (spec.pane) {
    const [label, command] = PANES[spec.pane] ?? [spec.pane, ""]
    const body = el("div", "native")
    body.append(el("div", "", { innerHTML: "<b></b><br>in the app's own pane: <span></span>" }))
    body.querySelector("b").textContent = label
    body.querySelector("span").textContent = command
    e._head = slotHead(spec.pane in PANES ? spec.pane : "page", label)
    e.append(e._head, body)
    e._show = () => {}
    e._stop = () => {}
  } else {
    const id = spec.page
    e._head = slotHead("page", pageInfo[id]?.title || spec.name)
    e._head.querySelector(".icon").replaceChildren(favicon(spec.url, spec.name))
    const bar = el("div", "app-chrome")
    const input = el("input", "urlbar", { value: pageInfo[id]?.url || spec.url, spellcheck: false, placeholder: "Enter a URL or search" })
    input.onfocus = () => input.select()
    const view = liveView(id)
    input.onkeydown = ev => {
      if (ev.key !== "Enter") return
      op({ op: "navigate", cell: id, url: input.value })
      view.querySelector(".input").focus()
    }
    bar.append(
      iconButton("back", "Back", () => op({ op: "back", cell: id })),
      iconButton("forward", "Forward", () => op({ op: "forward", cell: id })),
      iconButton("reload", "Reload", () => op({ op: "reload", cell: id })),
      input,
    )
    e.append(e._head, bar, view)
    Object.assign(e, { _id: id, _input: input, _title: e._head.querySelector(".title"), _canvas: view.querySelector("canvas") })
    sizing(e, view, id, spec)
  }
  headDrag(e)
  deck.append(e)
  live.set(k, e)
  return e
}

/** The live page follows its card's size: opened (or brought back) once the
 *  card settles; never while cards move or a drag is on; parked when hidden. */
function sizing(e, view, id, spec) {
  let shown = false
  let sized = ""
  let timer = null
  const fit = () => {
    clearTimeout(timer)
    if (!shown) return
    const wait = Math.max(0, settleUntil - performance.now())
    if (dragging || wait > 0) return void (timer = setTimeout(fit, dragging ? 120 : wait + 30))
    const r = view.getBoundingClientRect()
    if (r.width < 20 || r.height < 20) return
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    const w = Math.round((r.width * dpr) / 2) * 2
    const h = Math.round((r.height * dpr) / 2) * 2
    if (`${w}x${h}` === sized) return
    sized = `${w}x${h}`
    op({ op: "open", cell: id, url: spec.url, w, h, scale: dpr, keepInPanel: spec.keep === true })
  }
  const watch = new ResizeObserver(() => {
    clearTimeout(timer)
    timer = setTimeout(fit, 120)
  })
  watch.observe(view)
  e._fit = fit
  e._show = on => {
    if (on === shown) return
    shown = on
    if (on) return fit()
    clearTimeout(timer)
    sized = ""
    op({ op: "hide", cell: id })
  }
  e._stop = () => {
    clearTimeout(timer)
    watch.disconnect()
  }
}

/** The header's buttons, for where the card is: loose cards pin and close. */
function drawButtons(e) {
  const w = e._w
  const head = e._head
  head.querySelectorAll(".icon-btn").forEach(b => b.remove())
  const buttons = []
  if (e._id) {
    const address = iconButton("address", "Address bar", () => {
      e.classList.toggle("no-chrome")
      address.classList.toggle("active", !e.classList.contains("no-chrome"))
    })
    address.classList.toggle("active", !e.classList.contains("no-chrome"))
    buttons.push(address)
  }
  if (!w.inGrid) {
    const pin = iconButton("page", w.card.pinned ? "Unpin — apps stop landing here" : "Pin — apps land here", () => {
      cards = M.pinCard(cards, w.id)
      persist()
      layoutCards()
    })
    pin.innerHTML = MARKS.pin
    pin.classList.toggle("on", w.card.pinned)
    buttons.push(pin)
  }
  const isExpanded = expanded === w.id
  buttons.push(
    iconButton(isExpanded ? "restore" : "maximize", isExpanded ? "Restore" : "Expand", () => {
      expanded = isExpanded ? null : w.id
      layoutCards()
    }),
  )
  if (!w.inGrid) buttons.push(iconButton("close", "Close", () => closeCard(w.id)))
  head.append(...buttons)
}

function setDragging(on) {
  dragging = on
  document.body.classList.toggle("echo-dragging", on)
  if (!on) for (const e of live.values()) e._fit?.()
}

/** Drag a card by its head: onto another card to trade places, or to the
 *  band's side to give it a column of its own. */
function headDrag(e) {
  const head = e._head
  head.addEventListener("pointerdown", ev => {
    if (ev.button !== 0 || ev.target.closest("button") || expanded) return
    ev.preventDefault()
    const from = { x: ev.clientX, y: ev.clientY }
    let moved = false
    let target = null
    head.setPointerCapture(ev.pointerId)
    head.onpointermove = m => {
      const dx = m.clientX - from.x
      const dy = m.clientY - from.y
      if (!moved && Math.hypot(dx, dy) < 5) return
      if (!moved) {
        moved = true
        setDragging(true)
        e.classList.add("dragging")
      }
      e.style.transform = `translate(${dx}px, ${dy}px)`
      target = dropTarget(m.clientX, m.clientY, e)
      for (const other of live.values()) other.classList.toggle("drop", other === target?.card)
      showEdge(target?.side ?? null)
    }
    head.onpointerup = head.onpointercancel = () => {
      head.onpointermove = head.onpointerup = head.onpointercancel = null
      e.style.transform = ""
      e.classList.remove("dragging")
      for (const other of live.values()) other.classList.remove("drop")
      showEdge(null)
      setDragging(false)
      if (moved && target) dropCard(e._w, target)
    }
  })
}

function dropTarget(x, y, self) {
  const band = bandRect()
  if (!grid && cards.length > 1) {
    if (x < band.left + EDGE_PX) return { side: "left" }
    if (x > band.left + band.width - EDGE_PX) return { side: "right" }
  }
  for (const other of live.values()) {
    if (other === self || other.style.display === "none") continue
    const r = other.getBoundingClientRect()
    if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return { card: other }
  }
  return null
}

function showEdge(side) {
  edge.classList.toggle("on", side !== null)
  if (!side) return
  const band = bandRect()
  Object.assign(edge.style, { top: `${band.top}px`, height: `${band.height}px`, left: `${side === "left" ? band.left : band.left + band.width - 6}px` })
}

function dropCard(w, target) {
  if (target.side) cards = M.soloCard(cards, w.id, target.side)
  else if (grid) grid = M.swapCells(grid, w.id, target.card._w.id)
  else cards = M.swapCards(cards, w.id, target.card._w.id)
  persist()
  layoutCards()
}

// ── Seams ───────────────────────────────────────────────────────────────────
function drawSeams(band, want) {
  deck.querySelectorAll(".seam").forEach(s => s.remove())
  if (expanded) return
  if (grid) {
    const { cols, rows } = M.gridSeams(grid, band)
    for (const s of cols) seam("v", s.x, band.top, band.height, band.width, () => [...grid.colWidths], (start, shift) => (grid = { ...grid, colWidths: M.slideSeam(start, s.index, shift) }), saveShape)
    for (const s of rows) seam("h", band.left, s.y, band.width, band.height, () => [...grid.rowHeights], (start, shift) => (grid = { ...grid, rowHeights: M.slideSeam(start, s.index, shift) }), saveShape)
    return
  }
  const cols = M.flowColumns(cards)
  flowFr = M.syncFractions(cols, flowFr)
  const rect = c => want.get(c.fav).rect
  cols.forEach((col, ci) => {
    const r0 = rect(col[0])
    if (ci < cols.length - 1) {
      seam("v", r0.left + r0.width + M.GAP / 2, band.top, band.height, band.width, () => [...flowFr.colFr], (start, shift) => (flowFr = { ...flowFr, colFr: M.slideSeam(start, ci, shift) }))
    }
    if (col.length === 2) {
      seam("h", r0.left, r0.top + r0.height + M.GAP / 2, r0.width, band.height, () => [...flowFr.rowFr[ci]], (start, shift) => (flowFr = { ...flowFr, rowFr: flowFr.rowFr.map((f, i) => (i === ci ? M.slideSeam(start, 0, shift) : f)) }))
    }
  })
}

/** A seam between cards, dragged to share the space between its neighbours. */
function seam(axis, x, y, length, size, startOf, slide, done) {
  const s = el("div", `seam ${axis}`)
  const half = M.GAP / 2
  Object.assign(s.style, axis === "v" ? { left: `${x - half}px`, top: `${y}px`, height: `${length}px` } : { left: `${x}px`, top: `${y - half}px`, width: `${length}px` })
  s.onpointerdown = ev => {
    ev.preventDefault()
    s.setPointerCapture(ev.pointerId)
    s.classList.add("drag")
    setDragging(true)
    const start = startOf()
    const from = axis === "v" ? ev.clientX : ev.clientY
    s.onpointermove = m => {
      const moved = (axis === "v" ? m.clientX : m.clientY) - from
      slide(start, moved / size)
      layoutCards({ seams: false })
      s.style[axis === "v" ? "left" : "top"] = `${(axis === "v" ? x : y) - half + moved}px`
    }
    s.onpointerup = () => {
      s.onpointermove = s.onpointerup = null
      setDragging(false)
      layoutCards()
      done?.()
    }
  }
  deck.append(s)
}

/** A workspace's seams moved: kept in its file (the mod writes it). */
const saveShape = () => grid && api("/api/shape", { name: grid.workspace, colWidths: grid.colWidths, rowHeights: grid.rowHeights }).catch(() => {})

// ── Opening and closing ─────────────────────────────────────────────────────
/** A favourite as a card. Never two copies: one on stage stays where it is;
 *  one in a workspace on stage makes the grid loose cards first. */
function openFav(id) {
  if (grid?.cells.some(c => c.fav === id)) return flash(id)
  if (grid) {
    cards = M.dissolveGrid(grid, cards, newId)
    grid = null
  }
  if (cards.some(c => c.fav === id)) return flash(id)
  cards = M.openFavorite(cards, id, newId())
  expanded = null
  persist()
  render()
}

function flash(key) {
  const e = live.get(key)
  if (!e) return
  e.classList.add("drop")
  setTimeout(() => e.classList.remove("drop"), 600)
}

/** A workspace as its grid of cards: loose cards showing its favourites move
 *  into it; the rest wait, parked, behind it. */
function openWorkspace(name, tell = true) {
  const layout = layouts.find(l => l.name === name)
  if (!layout) return
  const r = M.workspaceGrid(layout, cards)
  grid = r.grid
  gridSource = JSON.stringify(layout)
  cards = r.cards
  expanded = null
  active = name
  if (tell) api("/api/active", { name }).catch(() => {})
  persist()
  render()
}

function closeCard(id) {
  cards = cards.filter(c => c.id !== id)
  if (expanded === id) expanded = null
  persist()
  render()
}

function closeAll() {
  grid = null
  cards = []
  expanded = null
  persist()
  render()
}

function render() {
  drawDock()
  drawWall()
  drawTuck()
  layoutCards()
}

// ── Keys, resizes, visibility ───────────────────────────────────────────────
document.addEventListener("keydown", e => {
  if (e.altKey && /^[1-9]$/.test(e.key)) {
    const l = layouts[Number(e.key) - 1]
    if (l) {
      e.preventDefault()
      W.hideEditor()
      openWorkspace(l.name)
    }
    return
  }
  if (e.key === "Escape") {
    if (folderOpen) return closeFolder()
    if (editing) return setEditing(false)
    if (expanded) {
      expanded = null
      return layoutCards()
    }
  }
  // Typing on the wall goes to the search.
  const onWall = !cardsUp() && !W.editorOpen() && !folderOpen && document.activeElement === document.body
  if (onWall && e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) search.focus()
})
let resizeTimer
addEventListener("resize", () => {
  settleUntil = performance.now() + SETTLE_MS
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    layoutCards()
    pages.scrollLeft = pageAt * pages.clientWidth
  }, 100)
})
document.addEventListener("visibilitychange", () => layoutCards())

// ── The helper's state ──────────────────────────────────────────────────────
function takeState(st) {
  layouts = Array.isArray(st.layouts) ? st.layouts : []
  settings = { ...settings, ...(st.settings ?? {}) }
  for (const p of st.pages ?? []) pageInfo[p.cell] = { url: p.url, title: p.title }
}

async function takeLibrary() {
  const next = await api("/api/library").catch(() => null)
  if (!next || !Array.isArray(next.favorites)) return
  lib = next
  if (lib.favorites.length || lib.workspaces.length) echo = M.pruneEcho(echo, M.tilesFrom(lib))
  cards = cards.filter(c => lib.favorites.some(f => f.id === c.fav))
}

/** The layouts, the settings or the active workspace changed (the mod's /dip
 *  among them): the page follows. */
async function refreshState() {
  if (!started) return
  const st = await api("/api/state").catch(() => null)
  if (!st) return
  takeState(st)
  await takeLibrary()
  if (grid) {
    const l = layouts.find(x => x.name === grid.workspace)
    if (!l) grid = null
    else if (JSON.stringify(l) !== gridSource) {
      grid = M.workspaceGrid(l, []).grid
      gridSource = JSON.stringify(l)
    }
  }
  if (typeof st.active === "string" && st.active && st.active !== active) return openWorkspace(st.active, false)
  render()
}

async function refreshLibrary() {
  if (!started) return
  await takeLibrary()
  persist()
  render()
}

/** The first paint: the kept wall put back before anything is saved. */
async function start() {
  const [st, kept] = await Promise.all([api("/api/state"), api("/api/echo")])
  takeState(st)
  active = typeof st.active === "string" ? st.active : ""
  echo = { order: kept.order, dock: kept.dock, folders: kept.folders }
  await takeLibrary()
  if (settings.home === "last workspace") {
    const wall = M.parseWall(kept.wall)
    cards = wall.cards.filter(c => lib.favorites.some(f => f.id === c.fav)).map(c => ({ ...c, id: newId() }))
    const name = wall.workspace ?? active
    const layout = layouts.find(l => l.name === name)
    if (layout) {
      const r = M.workspaceGrid(layout, cards)
      grid = r.grid
      gridSource = JSON.stringify(layout)
      cards = r.cards
      active = name
    }
  }
  started = true
  saver.restored()
  render()
}

window.WORKSPACES.ready("WORKSPACES_ECHO", {
  start,
  refreshState,
  refreshLibrary,
  openWorkspace: name => openWorkspace(name),
  /** The editor or the locked screen came or went: cards under it park. */
  layout: () => started && layoutCards(),
})
