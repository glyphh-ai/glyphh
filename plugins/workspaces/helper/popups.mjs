// popups.mjs — what a page may do outside its cell, after the Glyphh app's
// force-web.ts and home-view.ts (v1.6.2). A favourite can be "Keep in panel":
// a jump to a native app (slack://, msteams://, zoommtg://, …) is mapped back
// to its web client and loads in the same page, and so does a popup; a popup
// of about:blank is swallowed. Without it, a popup opens as a page of its own
// over the cell, closable, and a native app's link is opened by the Mac. Pure: the mod's
// tests load it as chrome.mjs does.

/** Web addresses (and about:) stay in the browser. */
export const isWebUrl = url => url.startsWith("http://") || url.startsWith("https://") || url.startsWith("about:")

/** A native app's address mapped to its web client; else the parent page's
 *  origin; null only when the parent's address is malformed too. */
export function nativeToWebUrl(nativeUrl, parentUrl) {
  try {
    const parsed = new URL(nativeUrl)
    const proto = parsed.protocol
    if (proto === "slack:") {
      const team = parsed.searchParams.get("team") || ""
      return team ? `https://app.slack.com/client/${team}` : "https://app.slack.com/client"
    }
    if (proto === "discord:") return "https://discord.com/app"
    if (proto === "msteams:") return "https://teams.microsoft.com"
    if (proto === "zoommtg:" || proto === "zoomus:") {
      const confno = parsed.searchParams.get("confno") || ""
      return confno ? `https://app.zoom.us/wc/${confno}/join` : "https://app.zoom.us"
    }
    if (proto === "notion:") return "https://notion.so"
  } catch {}
  try {
    return new URL(parentUrl).origin
  } catch {
    return null
  }
}

/** A popup the page opened: "same" loads `url` in the page itself, "swallow"
 *  and "deny" close it, "own" keeps it as a page of its own over the cell. */
export function popupDecision({ url, keepInPanel, parentUrl }) {
  if (keepInPanel) {
    if (url.startsWith("about:") || !url) return { action: "swallow" }
    const target = url.startsWith("http://") || url.startsWith("https://") ? url : nativeToWebUrl(url, parentUrl)
    return target ? { action: "same", url: target } : { action: "swallow" }
  }
  // about:blank keeps its page: a sign-in handoff writes into it.
  return url === "" || isWebUrl(url) ? { action: "own" } : { action: "deny" }
}

/** The native apps whose links the Mac may open for a page not kept in its
 *  panel; any other scheme (file:, chrome:, …) goes nowhere. */
const SYSTEM_SCHEMES = new Set(["slack:", "discord:", "msteams:", "zoommtg:", "zoomus:", "notion:", "mailto:"])

/** A native app's address the page went for (a link, or the page itself):
 *  kept in panel, its web client loads in the page ("same"); otherwise the
 *  Mac opens it, as for the app the link was for ("system"), when it is one
 *  of those apps. A web address is not native (null). */
export function nativeDecision({ url, keepInPanel, parentUrl }) {
  if (isWebUrl(url)) return null
  if (keepInPanel) {
    const web = nativeToWebUrl(url, parentUrl)
    return web ? { action: "same", url: web } : { action: "ignore" }
  }
  let scheme = ""
  try {
    scheme = new URL(url).protocol
  } catch {}
  return SYSTEM_SCHEMES.has(scheme) ? { action: "system", url } : { action: "ignore" }
}

/** The binding the page's link catcher calls with a native address. */
export const NATIVE_BINDING = "__workspacesNative"

/** Run in every page before its own scripts: a click on a link to a native
 *  app goes to the helper instead of to Chrome, whose prompt for an app it
 *  cannot open would hold the page's input for good. */
export const NATIVE_LINK_SCRIPT = `addEventListener("click", e => {
  const a = e.target && e.target.closest && e.target.closest("a[href]")
  if (!a || /^(https?|about|javascript|blob|data):/i.test(a.href)) return
  e.preventDefault()
  e.stopImmediatePropagation()
  ${NATIVE_BINDING}(a.href)
}, true)`

// Sites like Slack gate on a minimum Chrome version and refuse "Headless".
const MIN_CHROME_MAJOR = 137
const SPOOF_CHROME = "140.0.0.0"

/** A user agent with no Headless, Electron or app marks, its Chrome above the gate. */
export function cleanUserAgent(ua) {
  let out = ua
    .replace(/HeadlessChrome/g, "Chrome")
    .replace(/Electron\/\S+\s*/g, "")
    .replace(/\S+-client\/\S+\s*/g, "")
    .replace(/\s+/g, " ")
    .trim()
  const m = /Chrome\/(\d+)/.exec(out)
  if (m && parseInt(m[1], 10) < MIN_CHROME_MAJOR) out = out.replace(/Chrome\/[\d.]+/, `Chrome/${SPOOF_CHROME}`)
  return out
}

/** The client hints (Sec-CH-UA) that go with a clean user agent. */
export function userAgentMetadata(ua, { arm = false } = {}) {
  const full = /Chrome\/([\d.]+)/.exec(ua)?.[1] ?? SPOOF_CHROME
  const major = full.split(".")[0]
  const brands = v => [
    { brand: "Google Chrome", version: v },
    { brand: "Chromium", version: v },
    { brand: "Not=A?Brand", version: major === v ? "24" : "24.0.0.0" },
  ]
  const mac = /Macintosh/.test(ua)
  return {
    brands: brands(major),
    fullVersionList: brands(full),
    fullVersion: full,
    platform: mac ? "macOS" : /Windows/.test(ua) ? "Windows" : "Linux",
    platformVersion: "",
    architecture: arm ? "arm" : "x86",
    model: "",
    mobile: false,
    bitness: "64",
  }
}
