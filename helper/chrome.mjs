// chrome.mjs — the headless Chrome both helpers drive: one page per layout
// cell, each screencasting its frames, input replayed over CDP.
//
// startChrome({ format, onFrame, onNav, onTitle }) → { open, op, shutdown, run }
//   format   "png" (the terminal's Image reads PNG files) or "jpeg" (the
//            layout page's live stream)
//   onFrame  (page, bytes) for every frame, already acknowledged
//
// The profile is a lasting one (sign-ins kept) unless another Chrome holds it:
// then a throwaway one, so two sessions never fight over one profile.
//
// CDP runs over a private pipe (--remote-debugging-pipe, fds 3 and 4), never a
// port: no other program on the machine can attach to the signed-in Chrome.

import { spawn } from "node:child_process"
import { mkdtempSync, mkdirSync, readlinkSync, rmSync } from "node:fs"
import { homedir, tmpdir } from "node:os"
import { join } from "node:path"

const CHROME = process.env.WORKSPACES_CHROME
  || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
const LASTING = process.env.WORKSPACES_PROFILE
  || join(homedir(), "Library", "Application Support", "glyphh-workspaces", "chrome")

function isHeld(dir) {
  try {
    const target = readlinkSync(join(dir, "SingletonLock")) // "<host>-<pid>"
    process.kill(Number(target.split("-").pop()), 0)
    return true
  } catch {
    return false
  }
}

const KEYS = {
  return: ["Enter", 13, "\r"], enter: ["Enter", 13, "\r"], tab: ["Tab", 9, "\t"],
  backspace: ["Backspace", 8], delete: ["Delete", 46], up: ["ArrowUp", 38],
  down: ["ArrowDown", 40], left: ["ArrowLeft", 37], right: ["ArrowRight", 39],
  pageup: ["PageUp", 33], pagedown: ["PageDown", 34], home: ["Home", 36],
  end: ["End", 35], escape: ["Escape", 27],
}

export async function startChrome({ format = "jpeg", quality = 80, onFrame, onNav, onTitle, onExit }) {
  const run = mkdtempSync(join(tmpdir(), "glyphh-workspaces-"))
  mkdirSync(LASTING, { recursive: true })
  const profile = isHeld(LASTING) ? join(run, "profile") : LASTING
  const chrome = spawn(CHROME, [
    "--headless=new", "--remote-debugging-pipe", `--user-data-dir=${profile}`,
    "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--mute-audio",
    // Every cell is on screen at once: none may be treated as a background
    // tab (Chrome stops painting those, and their stream goes blank).
    "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    // The bridge page encodes cells as video with nobody clicking first.
    "--autoplay-policy=no-user-gesture-required",
    // WebRTC between this Chrome and the layout page, both on this machine:
    // real local addresses (no mDNS names), loopback allowed.
    "--allow-loopback-in-peer-connection",
    "--disable-features=WebRtcHideLocalIpsWithMdns",
    "about:blank",
  ], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] })
  chrome.on("exit", code => onExit?.(code))
  const toChrome = chrome.stdio[3]
  const fromChrome = chrome.stdio[4]

  let seq = 0
  const pending = new Map()
  const pages = new Map() // cell → page
  const sessions = new Map() // sessionId → cell

  const send = (method, params = {}, sessionId) => {
    const id = ++seq
    toChrome.write(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }) + "\0")
    return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
  }

  // Messages come NUL-terminated.
  let inbox = ""
  fromChrome.setEncoding("utf8")
  fromChrome.on("data", chunk => {
    inbox += chunk
    let end
    while ((end = inbox.indexOf("\0")) >= 0) {
      const raw = inbox.slice(0, end)
      inbox = inbox.slice(end + 1)
      if (raw) onMessage(JSON.parse(raw))
    }
  })

  function onMessage(msg) {
    if (msg.id) {
      const p = pending.get(msg.id)
      pending.delete(msg.id)
      if (p) msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result)
      return
    }
    const page = pages.get(sessions.get(msg.sessionId))
    if (!page) return
    if (msg.method === "Page.screencastFrame") {
      send("Page.screencastFrameAck", { sessionId: msg.params.sessionId }, page.session).catch(() => {})
      if (page.live) {
        page.gen += 1
        onFrame?.(page, Buffer.from(msg.params.data, "base64"))
      }
    } else if (msg.method === "Page.frameNavigated" && !msg.params.frame.parentId) {
      page.url = msg.params.frame.url
      onNav?.(page)
    } else if (msg.method === "Page.loadEventFired") {
      send("Runtime.evaluate", { expression: "document.title", returnByValue: true }, page.session)
        .then(r => { page.title = String(r?.result?.value ?? ""); onTitle?.(page) })
        .catch(() => {})
    }
  }

  let agent
  const userAgent = async () => {
    agent ??= (await send("Browser.getVersion")).userAgent.replace("HeadlessChrome", "Chrome")
    return agent
  }

  async function cast(page) {
    await send("Page.stopScreencast", {}, page.session).catch(() => {})
    if (!page.live) return
    await send("Page.startScreencast", {
      format, ...(format === "jpeg" ? { quality } : {}), maxWidth: page.w, maxHeight: page.h, everyNthFrame: 1,
    }, page.session)
  }

  async function size(page, w, h, scale = 1) {
    page.w = Math.max(64, Math.round(w))
    page.h = Math.max(48, Math.round(h))
    page.scale = scale
    await send("Emulation.setDeviceMetricsOverride", {
      width: Math.round(page.w / scale), height: Math.round(page.h / scale), deviceScaleFactor: scale, mobile: false,
    }, page.session)
    await cast(page)
  }

  /** Open a cell's page, or bring a parked one back at a (new) size. */
  async function open({ cell, url, w, h, scale = 1, cast: casts = true }) {
    let page = pages.get(cell)
    if (page) {
      const resized = page.w !== Math.round(w) || page.h !== Math.round(h) || page.scale !== scale
      if (resized) {
        page.live = true
        await size(page, w, h, scale)
      } else if (!page.live) {
        page.live = true
        await cast(page) // parked: back on
      }
      // Same size and already live: nothing to restart (a restart flashes a frame).
      return page
    }
    const { targetId } = await send("Target.createTarget", { url: "about:blank", newWindow: true, background: false })
    const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true })
    page = { cell, target: targetId, session: sessionId, w: 0, h: 0, scale: 1, gen: 0, live: casts, url, title: "" }
    pages.set(cell, page)
    sessions.set(sessionId, cell)
    await send("Page.enable", {}, sessionId)
    await send("Emulation.setFocusEmulationEnabled", { enabled: true }, sessionId)
    await send("Page.setWebLifecycleState", { state: "active" }, sessionId).catch(() => {})
    await send("Emulation.setUserAgentOverride", { userAgent: await userAgent() }, sessionId)
    await size(page, w, h, scale)
    await send("Page.navigate", { url }, sessionId)
    return page
  }

  async function key(page, { key, ctrl, shift, meta, alt }) {
    const mods = (alt ? 1 : 0) | (ctrl ? 2 : 0) | (meta ? 4 : 0) | (shift ? 8 : 0)
    const named = KEYS[key.toLowerCase()] ?? KEYS[key]
    if (!named && key.length === 1 && !ctrl && !meta && !alt) {
      await send("Input.insertText", { text: key }, page.session)
      return
    }
    const [k, code, text] = named ?? [key, key.toUpperCase().charCodeAt(0)]
    const base = { key: k, windowsVirtualKeyCode: code, modifiers: mods }
    await send("Input.dispatchKeyEvent", { type: text ? "keyDown" : "rawKeyDown", ...base, ...(text ? { text } : {}) }, page.session)
    await send("Input.dispatchKeyEvent", { type: "keyUp", ...base }, page.session)
  }

  /** One command for a cell's page (the open one above aside). */
  async function op(cmd) {
    if (cmd.op === "open") return open(cmd)
    const page = pages.get(cmd.cell)
    if (!page) return
    const s = page.session
    // Input arrives in the cell's CSS pixels; the page is laid out in those / scale.
    const at = v => (typeof v === "number" ? v : 0)
    switch (cmd.op) {
      case "resize": return size(page, cmd.w, cmd.h, cmd.scale ?? page.scale)
      case "hide": page.live = false; return send("Page.stopScreencast", {}, s)
      case "navigate": {
        const url = /^[a-z]+:/i.test(cmd.url) ? cmd.url : `https://${cmd.url}`
        return send("Page.navigate", { url }, s)
      }
      case "back": return send("Runtime.evaluate", { expression: "history.back()" }, s)
      case "forward": return send("Runtime.evaluate", { expression: "history.forward()" }, s)
      case "reload": return send("Page.reload", {}, s)
      case "mouse": return send("Input.dispatchMouseEvent", {
        type: { down: "mousePressed", up: "mouseReleased", move: "mouseMoved" }[cmd.action],
        x: at(cmd.x), y: at(cmd.y), button: cmd.button ?? "none",
        clickCount: cmd.action === "move" ? 0 : (cmd.clicks ?? 1),
        modifiers: cmd.mods ?? 0,
      }, s)
      case "wheel": return send("Input.dispatchMouseEvent", {
        type: "mouseWheel", x: cmd.x ?? page.w / 2, y: cmd.y ?? page.h / 2, deltaX: cmd.dx ?? 0, deltaY: cmd.dy ?? 0,
      }, s)
      case "key": return key(page, cmd)
      case "text": return send("Input.insertText", { text: String(cmd.text ?? "") }, s)
      case "close":
        pages.delete(cmd.cell)
        sessions.delete(s)
        return send("Target.closeTarget", { targetId: page.target })
    }
  }

  /** A cell's page as text, for Claude when the person lets it read. */
  async function text(cell, max = 60_000) {
    const page = pages.get(cell)
    if (!page) return undefined
    const r = await send("Runtime.evaluate", {
      expression: `(document.body ? document.body.innerText : "").slice(0, ${Number(max)})`,
      returnByValue: true,
    }, page.session)
    return { cell, url: page.url, title: page.title, text: String(r?.result?.value ?? "") }
  }

  let done = false
  function shutdown() {
    if (done) return
    done = true
    try { chrome.kill("SIGTERM") } catch {}
    setTimeout(() => { try { rmSync(run, { recursive: true, force: true }) } catch {} }, 300)
  }

  return { open, op, text, shutdown, run, pages }
}
