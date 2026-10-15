// chrome.mjs — the headless Chrome the layout page drives: one page per
// browser cell, each screencasting its JPEG frames, input replayed over CDP.
//
// startChrome({ quality, onFrame, onNav, onTitle, onPopup, onPopupClosed, onExit })
//   → { open, op, text, shutdown, pages }
//   onFrame  (page, bytes, { captured }) for every frame, already acknowledged;
//            `captured` is when Chrome took it, in ms since the epoch
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

import { addressOf, keyCalls, mouseCall, nulFramer } from "./input.mjs"
import { NATIVE_BINDING, NATIVE_LINK_SCRIPT, cleanUserAgent, nativeDecision, popupDecision, userAgentMetadata } from "./popups.mjs"

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

/** The isolated world the native-link catcher runs in. */
const WORLD = "workspaces"

/** The page a cell's popup is shown as, over the cell. */
export const popupCell = cell => `${cell}#popup`

export async function startChrome({ quality = 80, onFrame, onNav, onTitle, onPopup, onPopupClosed, onExit }) {
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

  fromChrome.setEncoding("utf8")
  fromChrome.on("data", nulFramer(onMessage))
  await send("Target.setDiscoverTargets", { discover: true }) // popups: Target.targetCreated

  function onMessage(msg) {
    if (msg.id) {
      const p = pending.get(msg.id)
      pending.delete(msg.id)
      if (p) msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result)
      return
    }
    if (!msg.sessionId) return onBrowser(msg)
    const page = pages.get(sessions.get(msg.sessionId))
    if (!page) return
    if (msg.method === "Page.windowOpen") {
      page.opening = msg.params.url // the popup's address: its target arrives next, without it
      return
    }
    if (msg.method === "Runtime.bindingCalled" && msg.params.name === NATIVE_BINDING) {
      void native(page, String(msg.params.payload), false).catch(() => {})
      return
    }
    if (msg.method === "Page.frameRequestedNavigation" && msg.params.frameId === page.target) {
      void native(page, msg.params.url, true).catch(() => {})
      return
    }
    if (msg.method === "Page.screencastFrame") {
      send("Page.screencastFrameAck", { sessionId: msg.params.sessionId }, page.session).catch(() => {})
      if (page.live) {
        page.gen += 1
        onFrame?.(page, Buffer.from(msg.params.data, "base64"), { captured: (msg.params.metadata?.timestamp ?? 0) * 1000 })
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

  // ── Popups ───────────────────────────────────────────────────────────────
  // A page's popup is a new target with the page as its opener. "Keep in
  // panel" pages load it in themselves (popups.mjs decides); the others show
  // it as a page of its own over the cell until it, or the person, closes it.

  function onBrowser(msg) {
    if (msg.method === "Target.targetCreated") {
      const info = msg.params.targetInfo
      if (info.type !== "page" || !info.openerId) return
      const opener = [...pages.values()].find(p => p.target === info.openerId)
      if (opener) void popup(opener, info).catch(() => {})
    } else if (msg.method === "Target.targetDestroyed") {
      const gone = [...pages.values()].find(p => p.target === msg.params.targetId && p.parent)
      if (gone) forget(gone)
    }
  }

  async function popup(opener, info) {
    const url = info.url || opener.opening || ""
    opener.opening = undefined
    const decision = popupDecision({ url, keepInPanel: opener.keep, parentUrl: opener.url })
    if (decision.action !== "own") {
      await send("Target.closeTarget", { targetId: info.targetId }).catch(() => {})
      if (decision.action === "same") await send("Page.navigate", { url: decision.url }, opener.session)
      return
    }
    const cell = popupCell(opener.cell)
    const was = pages.get(cell)
    if (was) await send("Target.closeTarget", { targetId: was.target }).catch(() => {})
    const { sessionId } = await send("Target.attachToTarget", { targetId: info.targetId, flatten: true })
    const page = { cell, parent: opener.cell, target: info.targetId, session: sessionId, w: 0, h: 0, scale: 1, gen: 0, live: true, keep: false, url, title: "" }
    pages.set(cell, page)
    sessions.set(sessionId, cell)
    await prepare(page)
    await size(page, opener.w, opener.h, opener.scale)
    onPopup?.(opener, page)
  }

  /** A native app's address the page went for. A link the page's catcher
   *  sent never reached Chrome; the page itself going there did, and Chrome's
   *  prompt for the app holds its input for good, so the page is made anew. */
  async function native(page, url, reachedChrome) {
    const decision = nativeDecision({ url, keepInPanel: page.keep, parentUrl: page.url })
    if (!decision) return
    if (decision.action === "system") spawn("open", [decision.url], { stdio: "ignore", detached: true }).unref()
    const next = decision.action === "same" ? decision.url : page.url
    if (reachedChrome) await renew(page, next)
    else if (decision.action === "same") await send("Page.navigate", { url: next }, page.session)
  }

  /** The page's target replaced by a fresh one at `url`, same cell and size. */
  async function renew(page, url) {
    const old = { target: page.target, session: page.session }
    const { targetId } = await send("Target.createTarget", { url: "about:blank", newWindow: true, background: false })
    const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true })
    sessions.delete(old.session)
    Object.assign(page, { target: targetId, session: sessionId, url })
    sessions.set(sessionId, page.cell)
    await prepare(page)
    await size(page, page.w, page.h, page.scale)
    await send("Page.navigate", { url }, sessionId)
    await send("Target.closeTarget", { targetId: old.target }).catch(() => {})
  }

  function forget(page) {
    pages.delete(page.cell)
    sessions.delete(page.session)
    onPopupClosed?.(page)
  }

  // ── A clean user agent: no "Headless", in the header and the client hints ──
  let agent
  const userAgent = async () => {
    if (!agent) {
      const version = await send("Browser.getVersion")
      const ua = cleanUserAgent(version.userAgent)
      agent = { userAgent: ua, userAgentMetadata: userAgentMetadata(ua, { arm: process.arch === "arm64" }) }
    }
    return agent
  }

  /** A page set up as a cell needs it: events, focus, lifecycle, user agent. */
  async function prepare(page) {
    const s = page.session
    await send("Page.enable", {}, s)
    await send("Emulation.setFocusEmulationEnabled", { enabled: true }, s)
    await send("Page.setWebLifecycleState", { state: "active" }, s).catch(() => {})
    const ua = await userAgent()
    await send("Network.setUserAgentOverride", ua, s)
    await send("Emulation.setUserAgentOverride", ua, s)
    // Links to native apps come to us (popups.mjs), in this page and its next,
    // from a world of our own: the page's scripts cannot call the binding.
    await send("Runtime.enable", {}, s)
    await send("Runtime.addBinding", { name: NATIVE_BINDING, executionContextName: WORLD }, s)
    await send("Page.addScriptToEvaluateOnNewDocument", { source: NATIVE_LINK_SCRIPT, worldName: WORLD }, s)
    const world = await send("Page.createIsolatedWorld", { frameId: page.target, worldName: WORLD }, s).catch(() => null)
    if (world) await send("Runtime.evaluate", { expression: NATIVE_LINK_SCRIPT, contextId: world.executionContextId }, s).catch(() => {})
  }

  async function cast(page) {
    await send("Page.stopScreencast", {}, page.session).catch(() => {})
    if (!page.live) return
    await send("Page.startScreencast", {
      format: "jpeg", quality, maxWidth: page.w, maxHeight: page.h, everyNthFrame: 1,
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
  async function open({ cell, url, w, h, scale = 1, keepInPanel = false }) {
    let page = pages.get(cell)
    if (page) {
      page.keep = keepInPanel
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
    page = { cell, target: targetId, session: sessionId, w: 0, h: 0, scale: 1, gen: 0, live: true, keep: keepInPanel, url, title: "" }
    pages.set(cell, page)
    sessions.set(sessionId, cell)
    await prepare(page)
    await size(page, w, h, scale)
    await send("Page.navigate", { url }, sessionId)
    return page
  }

  async function key(page, cmd) {
    for (const [method, params] of keyCalls(cmd)) await send(method, params, page.session)
  }

  /** One command for a cell's page (the open one above aside). */
  async function op(cmd) {
    if (cmd.op === "open") return open(cmd)
    const page = pages.get(cmd.cell)
    if (!page) return
    const s = page.session
    switch (cmd.op) {
      case "resize": return size(page, cmd.w, cmd.h, cmd.scale ?? page.scale)
      case "hide": page.live = false; return send("Page.stopScreencast", {}, s)
      case "navigate": return send("Page.navigate", { url: addressOf(String(cmd.url)) }, s)
      case "back": return send("Runtime.evaluate", { expression: "history.back()" }, s)
      case "forward": return send("Runtime.evaluate", { expression: "history.forward()" }, s)
      case "reload": return send("Page.reload", {}, s)
      case "mouse": return send(...mouseCall(cmd), s)
      case "wheel": return send("Input.dispatchMouseEvent", {
        type: "mouseWheel", x: cmd.x ?? page.w / 2, y: cmd.y ?? page.h / 2, deltaX: cmd.dx ?? 0, deltaY: cmd.dy ?? 0,
      }, s)
      case "key": return key(page, cmd)
      case "text": return send("Input.insertText", { text: String(cmd.text ?? "") }, s)
      case "close":
        if (page.parent) forget(page)
        else {
          pages.delete(cmd.cell)
          sessions.delete(s)
        }
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
