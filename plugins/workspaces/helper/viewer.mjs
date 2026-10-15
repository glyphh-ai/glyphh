// viewer.mjs — the layout page: one local web page that draws a whole layout,
// its browser cells live (headless Chrome via chrome.mjs, each page's JPEG
// frames streamed into the cell, clicks and keys sent back).
//
// Started by the mod, detached (WORKSPACES_DETACH=1: it starts itself again
// in a session of its own and the first copy exits), so it outlives the mod's
// reloads and the page stays up; the mod finds it again by the port and
// token it chose (WORKSPACES_PORT, WORKSPACES_TOKEN, kept in the session's
// memory) and the code's version (WORKSPACES_VERSION, in GET /api/state). It
// leaves when asked (POST /api/quit) or when the mod has not asked for its
// messages for 30 seconds. The mod posts the layouts and the library they come
// from (POST /api/layouts) and collects the helper's messages (GET
// /api/inbox): the shapes the person drags ({ t: "layout", name, colWidths,
// rowHeights }), the layout they pick in the page ({ t: "active", name }), and
// { t: "library", renamed? } once the page's workspace editor has written
// ~/.glyphh (WORKSPACES_LIBRARY), checked by ./library.mjs. The mod's licence
// module posts the licence's state in words (POST /api/licence-state) and
// collects the page's Unlock, Cancel and Copy (GET /api/licence-inbox). Started by hand,
// without a token, it picks its own and prints { t: "ready", port, token } and
// each message as a line.
//
// Locked to this machine and this page (./gate.mjs): it listens on 127.0.0.1
// only, on a random port; every request carries the session's random token
// (?t= or X-Token); Host must be 127.0.0.1:<port> (no DNS-rebinding name) and
// any Origin this page's; the page may not be framed. The token is the key to
// the signed-in Chrome and is never written anywhere: the page is opened with
// a one-time key (POST /api/key) and receives the token inside its HTML.
//
// Pictures: every cell's screencast JPEGs go to the page on one stream
// (GET /frames, multipart, each part naming its cell), which decodes them off
// its main thread and draws them. One connection for all cells, and nothing
// between Chrome's frame and the page but the socket: measured with
// WORKSPACES_DEBUG=1, this is how a click's picture arrives fastest.

import { execFile, spawn } from "node:child_process"
import { randomBytes } from "node:crypto"
import { mkdirSync, openSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs"
import { createServer } from "node:http"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

import { startChrome } from "./chrome.mjs"
import { isAllowed, isLocal, openKeys } from "./gate.mjs"
import { parseEcho } from "./echo-model.mjs"
import { faviconCandidates, faviconTarget, isIcon } from "./favicon.mjs"
import { checkFavorite, checkFavoriteDelete, checkWorkspace, checkWorkspaceDelete, pickedFolder } from "./library.mjs"

const HERE = dirname(fileURLToPath(import.meta.url))

// Detached: start again in a session of our own, the error output to a log
// (it never holds the token), and leave the mod's process tree.
if (process.env.WORKSPACES_DETACH === "1") {
  const log = openSync(join(tmpdir(), "glyphh-workspaces-helper.log"), "a")
  spawn(process.execPath, [fileURLToPath(import.meta.url)], {
    detached: true,
    stdio: ["ignore", "ignore", log],
    env: { ...process.env, WORKSPACES_DETACH: "" },
  }).unref()
  process.exit(0)
}

const MANAGED = Boolean(process.env.WORKSPACES_TOKEN)
const TOKEN = process.env.WORKSPACES_TOKEN || randomBytes(24).toString("hex")
const VERSION = process.env.WORKSPACES_VERSION || ""
const inbox = []
let heardFrom = Date.now()
/** A message for the mod: kept for GET /api/inbox, and printed when run by hand. */
const say = msg => {
  if (MANAGED) inbox.push(msg)
  else process.stdout.write(JSON.stringify(msg) + "\n")
}
// WORKSPACES_DEBUG=1: the layout page measures input → picture (./debug).
const DEBUG = process.env.WORKSPACES_DEBUG === "1"
const trace = { ops: [], frames: [] }
const keep = (list, item) => { list.push(item); if (list.length > 5000) list.shift() }
const withFlags = html => html.replace("__WORKSPACES_TOKEN__", TOKEN).replace("__WORKSPACES_DEBUG__", String(DEBUG))
const KEYS = openKeys({ random: () => randomBytes(24).toString("hex") })

let layouts = []
let active = ""
let library = { workspaces: [], favorites: [], choices: { models: [], efforts: [] } }
let picking = false
let settings = {}
const favicons = new Map() // site origin → { type, bytes } | null, for this helper's life
// The licence as the mod tells it (its state in words, never the licence),
// and what the page asked of it, for the mod to collect.
let licenceState = null
const licenceAsks = []
const LICENCE_ACTIONS = ["buy", "cancel", "copy"]
const LIBRARY = process.env.WORKSPACES_LIBRARY || ""

/** A file written whole or not at all: to a temporary name, then moved. */
function writeAtomic(path, value) {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(`${path}.tmp`, `${JSON.stringify(value, null, 2)}\n`)
  renameSync(`${path}.tmp`, path)
}

const workspacePath = slug => join(LIBRARY, "workspaces", `${slug}.json`)
const ASSETS = {
  "/ws/workspaces.js": "text/javascript",
  "/ws/grid.mjs": "text/javascript",
  "/ws/workspaces.css": "text/css",
  "/ws/echo.js": "text/javascript",
  "/ws/echo-model.mjs": "text/javascript",
  "/ws/echo.css": "text/css",
}

/** Fetched with a time limit and a size limit; null on any failure. */
async function fetchLimited(url, limit) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5000), redirect: "follow", headers: { "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/140.0.0.0 Safari/537.36" } })
    if (!res.ok) return null
    const bytes = Buffer.from(await res.arrayBuffer())
    return bytes.length <= limit ? { type: res.headers.get("content-type") ?? "", bytes } : null
  } catch {
    return null
  }
}

/** A favourite's icon: the ones its page names, else /favicon.ico. */
async function favicon(target) {
  if (favicons.has(target.origin)) return favicons.get(target.origin)
  const page = await fetchLimited(target.href, 1024 * 1024)
  let icon = null
  for (const url of faviconCandidates(target.href, page?.bytes.toString("utf8") ?? "")) {
    const got = await fetchLimited(url, 512 * 1024)
    if (got && isIcon(got.type, got.bytes.length)) {
      icon = got
      break
    }
  }
  favicons.set(target.origin, icon)
  return icon
}

const echoPath = () => join(LIBRARY, "echo.json")
function readEcho() {
  try {
    return parseEcho(JSON.parse(readFileSync(echoPath(), "utf8")))
  } catch {
    return parseEcho(null)
  }
}

// ── Streams ─────────────────────────────────────────────────────────────────

const BOUNDARY = "glyphhframe"
const frameStreams = new Set() // GET /frames responses
const last = new Map() // cell → { bytes, captured }: the newest frame, for a page that joins
const events = new Set() // SSE responses (pages)

function writeFrame(res, cell, bytes, captured) {
  res.write(`--${BOUNDARY}\r\nContent-Type: image/jpeg\r\nX-Cell: ${encodeURIComponent(cell)}\r\nX-Captured: ${captured}\r\nContent-Length: ${bytes.length}\r\n\r\n`)
  res.write(bytes)
  res.write("\r\n")
}

function emit(msg) {
  const line = `data: ${JSON.stringify(msg)}\n\n`
  for (const e of events) e.res.write(line)
}

// Chrome starts while the server already listens; a request waits for it.
const chromeReady = startChrome({
  quality: 80,
  onFrame(page, bytes, { captured }) {
    last.set(page.cell, { bytes, captured })
    if (DEBUG) keep(trace.frames, { cell: page.cell, captured, received: Date.now(), size: bytes.length })
    for (const res of frameStreams) writeFrame(res, page.cell, bytes, captured)
  },
  onNav: page => emit({ t: "nav", cell: page.cell, url: page.url }),
  onPopup: (opener, page) => emit({ t: "popup", cell: opener.cell, popup: page.cell, url: page.url }),
  onPopupClosed: page => {
    last.delete(page.cell)
    emit({ t: "popup-closed", cell: page.parent, popup: page.cell })
  },
  onTitle: page => emit({ t: "title", cell: page.cell, title: page.title }),
  onExit: () => shutdown(1),
})

// ── The gate ────────────────────────────────────────────────────────────────

let port = 0
const allowed = (req, url) =>
  isAllowed({ host: req.headers.host, origin: req.headers.origin, token: url.searchParams.get("t") ?? req.headers["x-token"] }, { port, secret: TOKEN })

/** The page, opened by a one-time key; the token goes inside it. */
function page(req, url, res) {
  if (!isLocal({ host: req.headers.host, origin: req.headers.origin }, port) || !KEYS.consume(url.searchParams.get("k"), Date.now())) {
    res.writeHead(403, { ...SECURITY, "Content-Type": "text/html; charset=utf-8" })
    res.end("<!doctype html><meta charset=utf-8><title>Workspaces</title><p style=\"font:14px -apple-system,sans-serif;padding:24px\">This layout page has been opened already. Run <b>/stream</b> in Claude to open it again.</p>")
    return
  }
  res.writeHead(200, { ...SECURITY, "Content-Type": "text/html; charset=utf-8" })
  res.end(withFlags(readFileSync(join(HERE, "viewer.html"), "utf8")))
}

const pagesOpen = () => events.size
let opsDone = Promise.resolve()

const SECURITY = {
  "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Cache-Control": "no-store",
}

const readBody = req => new Promise(resolve => {
  let body = ""
  req.on("data", c => { body += c; if (body.length > 1e6) req.destroy() })
  req.on("end", () => { try { resolve(JSON.parse(body || "null")) } catch { resolve(null) } })
})

const json = (res, value, status = 200) => {
  res.writeHead(status, { ...SECURITY, "Content-Type": "application/json" })
  res.end(JSON.stringify(value))
}

// ── Routes ──────────────────────────────────────────────────────────────────

chromeReady.catch(err => {
  process.stderr.write(`Chrome did not start: ${err?.message ?? err}\n`)
  shutdown(1)
})
let chrome
const server = createServer(async (req, res) => {
  chrome = await chromeReady
  const url = new URL(req.url ?? "/", `http://127.0.0.1:${port}`)
  if (req.method === "GET" && url.pathname === "/" && url.searchParams.has("k")) return page(req, url, res)
  if (!allowed(req, url)) {
    res.writeHead(403, SECURITY)
    res.end("forbidden")
    return
  }
  const route = `${req.method} ${url.pathname}`
  try {
    if (route === "POST /api/key") {
      json(res, { key: KEYS.issue(Date.now()) })
    } else if (route === "GET /api/text") {
      json(res, (await chrome.text(url.searchParams.get("cell") ?? "")) ?? { error: "no such page" })
    } else if (route === "GET /api/state") {
      json(res, {
        version: VERSION, layouts, active, settings, open: pagesOpen(),
        pages: [...chrome.pages.values()].map(p => ({ cell: p.cell, url: p.url, title: p.title })),
      })
    } else if (route === "POST /api/active") {
      const body = await readBody(req)
      if (typeof body?.name === "string") active = body.name
      say({ t: "active", name: active })
      json(res, {})
    } else if (route === "POST /api/layouts") {
      const body = await readBody(req)
      if (Array.isArray(body?.layouts)) layouts = body.layouts
      if (typeof body?.active === "string") active = body.active
      if (body?.settings && typeof body.settings === "object") settings = body.settings
      if (Array.isArray(body?.library?.workspaces) && Array.isArray(body?.library?.favorites)) {
        library = { workspaces: body.library.workspaces, favorites: body.library.favorites, choices: body.library.choices ?? { models: [], efforts: [] } }
      }
      emit({ t: "state" })
      json(res, {})
    } else if (route === "POST /api/shape") {
      const body = await readBody(req)
      const l = layouts.find(x => x.name === body?.name)
      if (l && Array.isArray(body.colWidths) && Array.isArray(body.rowHeights)) {
        l.colWidths = body.colWidths
        l.rowHeights = body.rowHeights
        say({ t: "layout", name: l.name, colWidths: l.colWidths, rowHeights: l.rowHeights })
      }
      json(res, {})
    } else if (DEBUG && route === "GET /debug/probe") {
      res.writeHead(200, { ...SECURITY, "Content-Type": "text/html; charset=utf-8" })
      res.end(readFileSync(join(HERE, "debug", "probe.html")))
    } else if (DEBUG && route === "GET /api/debug") {
      json(res, trace)
    } else if (route === "GET /api/inbox") {
      heardFrom = Date.now()
      json(res, { messages: inbox.splice(0) })
    } else if (route === "POST /api/quit") {
      json(res, {})
      shutdown(0)
    } else if (route === "GET /api/library") {
      json(res, library)
    } else if (route === "POST /api/workspace" || route === "POST /api/workspace/delete" || route === "POST /api/favorite" || route === "POST /api/favorite/delete") {
      if (!LIBRARY) return json(res, { error: "There is nowhere to save: HOME is not set." }, 500)
      const body = await readBody(req)
      const done = saveLibrary(url.pathname, body)
      if (done.error) return json(res, { error: done.error }, 400)
      emit({ t: "library" })
      json(res, done)
    } else if (route === "GET /api/favicon") {
      const target = faviconTarget(url.searchParams.get("url"))
      const icon = target && (await favicon(target))
      if (!icon) {
        res.writeHead(404, SECURITY)
        return res.end()
      }
      res.writeHead(200, { ...SECURITY, "Content-Type": icon.type, "Cache-Control": "private, max-age=86400" })
      res.end(icon.bytes)
    } else if (route === "GET /api/echo") {
      json(res, LIBRARY ? readEcho() : parseEcho(null))
    } else if (route === "POST /api/echo") {
      if (!LIBRARY) return json(res, { error: "There is nowhere to save: HOME is not set." }, 500)
      const echo = parseEcho(await readBody(req))
      writeAtomic(echoPath(), echo)
      json(res, { ok: true })
    } else if (route === "POST /api/licence-state") {
      const body = await readBody(req)
      licenceState = body?.status ?? null
      emit({ t: "licence", status: licenceState })
      json(res, {})
    } else if (route === "GET /api/licence-state") {
      json(res, { status: licenceState })
    } else if (route === "POST /api/licence") {
      const body = await readBody(req)
      if (!LICENCE_ACTIONS.includes(body?.action)) return json(res, { error: "unknown action" }, 400)
      licenceAsks.push(body.action)
      json(res, {})
    } else if (route === "GET /api/licence-inbox") {
      json(res, { actions: licenceAsks.splice(0) })
    } else if (route === "POST /api/pick-folder") {
      // The Mac's own folder chooser, in front of the app that is in front.
      if (picking) return json(res, { error: "The folder chooser is already open." }, 409)
      picking = true
      const script = 'tell application (path to frontmost application as text) to POSIX path of (choose folder with prompt "Choose the workspace folder")'
      execFile("osascript", ["-e", script], { timeout: 10 * 60_000 }, (err, stdout) => {
        picking = false
        json(res, { path: pickedFolder({ code: err ? 1 : 0, stdout }) })
      })
    } else if (route === "POST /api/show") {
      const body = await readBody(req)
      emit({ t: "show", view: body?.view === "favorites" ? "favorites" : "workspaces" })
      json(res, {})
    } else if (req.method === "GET" && ASSETS[url.pathname]) {
      res.writeHead(200, { ...SECURITY, "Content-Type": `${ASSETS[url.pathname]}; charset=utf-8` })
      res.end(readFileSync(join(HERE, url.pathname.slice(4))))
    } else if (route === "POST /api/ops") {
      const arrived = Date.now()
      const body = await readBody(req)
      // One op after another, across requests too: a release never overtakes its
      // press. An op Chrome never answers (a click that set off a native app's
      // link holds its release) holds the rest for 2 s at most.
      opsDone = opsDone.then(async () => {
        for (const cmd of [].concat(body ?? [])) {
          const sent = Date.now()
          await Promise.race([chrome.op(cmd).catch(() => {}), new Promise(r => setTimeout(r, 2000))])
          if (DEBUG && cmd.seq) keep(trace.ops, { seq: cmd.seq, op: cmd.op, action: cmd.action, cell: cmd.cell, input: cmd.t, posted: cmd.posted, arrived, sent, done: Date.now() })
        }
      })
      await opsDone
      json(res, {})
    } else if (route === "GET /frames") {
      res.writeHead(200, { ...SECURITY, "Content-Type": `multipart/mixed; boundary=${BOUNDARY}`, Connection: "keep-alive" })
      frameStreams.add(res)
      for (const [cell, f] of last) writeFrame(res, cell, f.bytes, f.captured)
      req.on("close", () => frameStreams.delete(res))
    } else if (route === "GET /events") {
      res.writeHead(200, { ...SECURITY, "Content-Type": "text/event-stream", Connection: "keep-alive" })
      res.write(": hello\n\n")
      const entry = { res }
      events.add(entry)
      req.on("close", () => events.delete(entry))
    } else {
      res.writeHead(404, SECURITY)
      res.end("not found")
    }
  } catch (err) {
    json(res, { error: String(err?.message ?? err) }, 500)
  }
})

// ── The workspace editor's saves ────────────────────────────────────────────

/** One save from the editor, checked, written, and told to the mod. */
function saveLibrary(path, body) {
  const { workspaces, favorites } = library
  if (path === "/api/workspace") {
    const ok = checkWorkspace(body, library)
    if (ok.error) return ok
    writeAtomic(workspacePath(ok.slug), ok.file)
    if (ok.replaces) unlinkSync(workspacePath(ok.replaces))
    const kept = workspaces.filter(w => w.slug !== ok.slug && w.slug !== ok.replaces)
    const at = workspaces.findIndex(w => w.slug === (ok.replaces ?? ok.slug))
    kept.splice(at < 0 ? kept.length : at, 0, { slug: ok.slug, file: ok.file })
    library = { ...library, workspaces: kept }
    say({ t: "library", ...(ok.replaces ? { renamed: { from: ok.replaces, to: ok.slug, name: ok.file.name, was: body.original } } : {}) })
    return { ok: true, name: ok.file.name }
  }
  if (path === "/api/workspace/delete") {
    const ok = checkWorkspaceDelete(String(body?.name ?? ""), workspaces)
    if (ok.error) return ok
    unlinkSync(workspacePath(ok.slug))
    library = { ...library, workspaces: workspaces.filter(w => w.slug !== ok.slug) }
    say({ t: "library" })
    return { ok: true }
  }
  const ok = path === "/api/favorite" ? checkFavorite(body, favorites) : checkFavoriteDelete(String(body?.id ?? ""), favorites, workspaces)
  if (ok.error) return ok
  writeAtomic(join(LIBRARY, "favorites.json"), { favorites: ok.favorites })
  library = { ...library, favorites: ok.favorites }
  say({ t: "library" })
  return { ok: true, ...(ok.id ? { id: ok.id } : {}) }
}

// ── Life ────────────────────────────────────────────────────────────────────

let done = false
function shutdown(code = 0) {
  if (done) return
  done = true
  try { server.close() } catch {}
  chromeReady.then(c => c.shutdown(), () => {})
  setTimeout(() => process.exit(code), 400)
}
for (const sig of ["SIGTERM", "SIGINT", "SIGHUP"]) process.on(sig, () => shutdown(0))
if (MANAGED) setInterval(() => { if (Date.now() - heardFrom > 30_000) shutdown(0) }, 5000).unref()
else {
  const parent = process.ppid
  setInterval(() => { if (process.ppid !== parent) shutdown(0) }, 2000).unref()
}

server.on("error", () => shutdown(1)) // the port is taken: the mod tries another
server.listen(Number(process.env.WORKSPACES_PORT) || 0, "127.0.0.1", () => {
  port = server.address().port
  if (!MANAGED) process.stdout.write(JSON.stringify({ t: "ready", port, token: TOKEN }) + "\n")
})
