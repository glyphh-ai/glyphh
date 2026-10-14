// viewer.mjs — the layout page: one local web page that draws a whole layout,
// its browser cells live (headless Chrome via chrome.mjs, each page's JPEG
// frames streamed into the cell, clicks and keys sent back).
//
// Started by the mod with the layouts in WORKSPACES_LAYOUTS (JSON) and the one
// to show in WORKSPACES_ACTIVE. Prints one line, { t: "ready", url }, and the
// layout shapes the person drags ({ t: "layout", name, colWidths, rowHeights }).
//
// Locked to this machine and this page: it listens on 127.0.0.1 only, on a
// random port; every request carries a random token (?t= or X-Token); Host
// must be 127.0.0.1:<port> (no DNS-rebinding name) and any Origin this page's;
// the page may not be framed. The token is the key to the signed-in Chrome.
//
// Video: each browser cell is WebRTC. A hidden bridge page in the same Chrome
// (bridge.html) draws the cell's frames on a canvas and sends it as video to
// the layout page; this server only passes the offer and answer along. The
// JPEG stream stays as the fallback and as the bridge's own source.

import { randomBytes, timingSafeEqual } from "node:crypto"
import { readFileSync } from "node:fs"
import { createServer } from "node:http"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

import { startChrome } from "./chrome.mjs"

const say = msg => process.stdout.write(JSON.stringify(msg) + "\n")
const HERE = dirname(fileURLToPath(import.meta.url))
const TOKEN = randomBytes(24).toString("hex")

let layouts = []
try { layouts = JSON.parse(process.env.WORKSPACES_LAYOUTS || "[]") } catch {}
let active = process.env.WORKSPACES_ACTIVE || layouts[0]?.name || ""

// ── Streams ─────────────────────────────────────────────────────────────────

const BOUNDARY = "glyphhframe"
const viewers = new Map() // cell → Set<res>
const last = new Map() // cell → last JPEG
const events = new Set() // SSE responses: { res, role: "page" | "bridge" }
const offers = new Map() // cell → { sdp, w, h } waiting for the bridge

function writeFrame(res, bytes) {
  res.write(`--${BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ${bytes.length}\r\n\r\n`)
  res.write(bytes)
  res.write("\r\n")
}

function emit(msg, role = "page") {
  const line = `data: ${JSON.stringify(msg)}\n\n`
  let sent = 0
  for (const e of events) if (e.role === role) { e.res.write(line); sent++ }
  return sent
}

let bridgeOpening
function ensureBridge() {
  bridgeOpening ??= chrome.open({
    cell: "__bridge__", url: `http://127.0.0.1:${port}/bridge?t=${TOKEN}`, w: 320, h: 240, cast: false,
  }).catch(err => { bridgeOpening = undefined; throw err })
  return bridgeOpening
}

const chrome = await startChrome({
  format: "jpeg",
  quality: 80,
  onFrame(page, bytes) {
    last.set(page.cell, bytes)
    for (const res of viewers.get(page.cell) ?? []) writeFrame(res, bytes)
  },
  onNav: page => emit({ t: "nav", cell: page.cell, url: page.url }),
  onTitle: page => emit({ t: "title", cell: page.cell, title: page.title }),
  onExit: () => shutdown(1),
})

// ── The gate ────────────────────────────────────────────────────────────────

let port = 0
const tokenOk = given => {
  if (typeof given !== "string" || given.length !== TOKEN.length) return false
  return timingSafeEqual(Buffer.from(given), Buffer.from(TOKEN))
}

function allowed(req, url) {
  if (req.headers.host !== `127.0.0.1:${port}`) return false
  const origin = req.headers.origin
  if (origin && origin !== `http://127.0.0.1:${port}`) return false
  return tokenOk(url.searchParams.get("t") ?? req.headers["x-token"])
}

const SECURITY = {
  "Content-Security-Policy": "default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
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

const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://127.0.0.1:${port}`)
  if (!allowed(req, url)) {
    res.writeHead(403, SECURITY)
    res.end("forbidden")
    return
  }
  const route = `${req.method} ${url.pathname}`
  try {
    if (route === "GET /") {
      res.writeHead(200, { ...SECURITY, "Content-Type": "text/html; charset=utf-8" })
      res.end(readFileSync(join(HERE, "viewer.html")))
    } else if (route === "GET /bridge") {
      res.writeHead(200, { ...SECURITY, "Content-Type": "text/html; charset=utf-8" })
      res.end(readFileSync(join(HERE, "bridge.html")))
    } else if (route === "POST /api/rtc") {
      const body = await readBody(req)
      const cell = String(body?.cell ?? "")
      if (body?.kind === "offer") {
        const offer = { sdp: String(body.sdp), w: Number(body.w) || 0, h: Number(body.h) || 0 }
        offers.set(cell, offer)
        await ensureBridge()
        if (emit({ t: "offer", cell, ...offer }, "bridge")) offers.delete(cell)
      } else if (body?.kind === "resize") {
        emit({ t: "resize", cell, w: Number(body.w) || 0, h: Number(body.h) || 0 }, "bridge")
      } else if (body?.kind === "answer") {
        emit({ t: "answer", cell, sdp: String(body.sdp) })
      } else if (body?.kind === "close") {
        offers.delete(cell)
        emit({ t: "close", cell }, "bridge")
      } else if (body?.kind === "error") {
        emit({ t: "rtc-error", cell, error: String(body.error) })
      }
      json(res, {})
    } else if (route === "GET /api/text") {
      json(res, (await chrome.text(url.searchParams.get("cell") ?? "")) ?? { error: "no such page" })
    } else if (route === "GET /api/state") {
      json(res, { layouts, active, pages: [...chrome.pages.values()].filter(p => p.cell !== "__bridge__").map(p => ({ cell: p.cell, url: p.url, title: p.title })) })
    } else if (route === "POST /api/active") {
      const body = await readBody(req)
      if (typeof body?.name === "string") active = body.name
      say({ t: "active", name: active })
      json(res, {})
    } else if (route === "POST /api/layouts") {
      const body = await readBody(req)
      if (Array.isArray(body?.layouts)) layouts = body.layouts
      if (typeof body?.active === "string") active = body.active
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
    } else if (route === "POST /api/ops") {
      const body = await readBody(req)
      for (const cmd of [].concat(body ?? [])) await chrome.op(cmd).catch(() => {})
      json(res, {})
    } else if (route === "GET /stream") {
      const cell = url.searchParams.get("cell") ?? ""
      res.writeHead(200, { ...SECURITY, "Content-Type": `multipart/x-mixed-replace; boundary=${BOUNDARY}`, Connection: "keep-alive" })
      const set = viewers.get(cell) ?? new Set()
      viewers.set(cell, set)
      set.add(res)
      if (last.has(cell)) writeFrame(res, last.get(cell))
      req.on("close", () => set.delete(res))
    } else if (route === "GET /events") {
      res.writeHead(200, { ...SECURITY, "Content-Type": "text/event-stream", Connection: "keep-alive" })
      res.write(": hello\n\n")
      const entry = { res, role: url.searchParams.get("role") === "bridge" ? "bridge" : "page" }
      events.add(entry)
      req.on("close", () => events.delete(entry))
      // Offers made before the bridge was listening.
      if (entry.role === "bridge") {
        for (const [cell, offer] of offers) emit({ t: "offer", cell, ...offer }, "bridge")
        offers.clear()
      }
    } else {
      res.writeHead(404, SECURITY)
      res.end("not found")
    }
  } catch (err) {
    json(res, { error: String(err?.message ?? err) }, 500)
  }
})

// ── Life ────────────────────────────────────────────────────────────────────

let done = false
function shutdown(code = 0) {
  if (done) return
  done = true
  try { server.close() } catch {}
  chrome.shutdown()
  setTimeout(() => process.exit(code), 400)
}
for (const sig of ["SIGTERM", "SIGINT", "SIGHUP"]) process.on(sig, () => shutdown(0))
const parent = process.ppid
setInterval(() => { if (process.ppid !== parent) shutdown(0) }, 2000).unref()

server.listen(0, "127.0.0.1", () => {
  port = server.address().port
  say({ t: "ready", url: `http://127.0.0.1:${port}/?t=${TOKEN}`, port })
})
