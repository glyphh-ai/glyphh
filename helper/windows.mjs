// windows.mjs — a layout as real Chrome windows, tiled on screen.
//
// Launches a visible Chrome on the workspaces profile (sign-ins kept) and
// opens one window per browser cell, placed by the layout's grid inside the
// screen area given (default: the right 65% of the main screen, leaving
// Claude its side). Usage:
//
//   node windows.mjs '<layout json>' [left top width height]

import { spawn, execFileSync } from "node:child_process"
import { mkdirSync, readFileSync, rmSync, existsSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

const CHROME = process.env.WORKSPACES_CHROME
  || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
const PROFILE = process.env.WORKSPACES_PROFILE
  || join(homedir(), "Library", "Application Support", "glyphh-workspaces", "chrome")

const layout = JSON.parse(process.argv[2])
const area = process.argv.length >= 7
  ? process.argv.slice(3, 7).map(Number)
  : defaultArea()

function defaultArea() {
  // Finder's desktop bounds: "0, 0, 1728, 1117" (menu bar included).
  const out = execFileSync("osascript", ["-e", 'tell application "Finder" to get bounds of window of desktop'])
    .toString().trim().split(",").map(s => Number(s.trim()))
  const [, , w, h] = out
  const top = 38 // under the menu bar
  const left = Math.round(w * 0.35)
  return [left, top, w - left, h - top]
}

/** Each browser cell's rectangle, from the grid's fractions. */
function rects([left, top, width, height]) {
  const edges = (fr, size) => {
    const sum = fr.reduce((a, b) => a + b, 0) || 1
    const out = [0]
    for (const f of fr) out.push(out[out.length - 1] + (f / sum) * size)
    return out.map(Math.round)
  }
  const xs = edges(layout.colWidths, width)
  const ys = edges(layout.rowHeights, height)
  return layout.cells
    .filter(c => c.panel === "browser" && c.url)
    .map(c => {
      const span = c.rowSpan ?? 1
      return {
        url: c.url,
        left: left + xs[c.col],
        top: top + ys[c.row],
        width: xs[c.col + 1] - xs[c.col],
        height: ys[c.row + span] - ys[c.row],
      }
    })
}

mkdirSync(PROFILE, { recursive: true })
rmSync(join(PROFILE, "DevToolsActivePort"), { force: true })
const chrome = spawn(CHROME, [
  "--remote-debugging-port=0",
  `--user-data-dir=${PROFILE}`,
  "--no-first-run",
  "--no-default-browser-check",
  "about:blank",
], { stdio: "ignore", detached: true })
chrome.unref()

async function devtoolsUrl() {
  const file = join(PROFILE, "DevToolsActivePort")
  for (let i = 0; i < 200; i++) {
    if (existsSync(file)) {
      const [port, path] = readFileSync(file, "utf8").trim().split("\n")
      if (port && path) return `ws://127.0.0.1:${port}${path}`
    }
    await new Promise(r => setTimeout(r, 50))
  }
  throw new Error("chrome never opened its debugging port (another Chrome on this profile?)")
}

const ws = new WebSocket(await devtoolsUrl())
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
let seq = 0
const pending = new Map()
ws.onmessage = ev => {
  const m = JSON.parse(ev.data)
  const p = m.id && pending.get(m.id)
  if (!p) return
  pending.delete(m.id)
  m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result)
}
const send = (method, params = {}) => {
  const id = ++seq
  ws.send(JSON.stringify({ id, method, params }))
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
}

// The launch window (about:blank) goes; each cell gets its own window.
const { targetInfos } = await send("Target.getTargets")
const blank = targetInfos.filter(t => t.type === "page")
for (const r of rects(area)) {
  const { targetId } = await send("Target.createTarget", { url: r.url, newWindow: true })
  const { windowId } = await send("Browser.getWindowForTarget", { targetId })
  await send("Browser.setWindowBounds", { windowId, bounds: { windowState: "normal" } })
  await send("Browser.setWindowBounds", {
    windowId,
    bounds: { left: r.left, top: r.top, width: r.width, height: r.height },
  })
}
for (const t of blank) await send("Target.closeTarget", { targetId: t.targetId }).catch(() => {})
console.log(JSON.stringify({ t: "tiled", layout: layout.name, area }))
ws.close()
process.exit(0)
