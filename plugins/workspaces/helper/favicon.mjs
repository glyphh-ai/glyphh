// favicon.mjs — where a favourite's icon is found, for the helper's favicon
// proxy (GET /api/favicon?url=…, token-checked like every route). Pure: the
// mod's tests load it as the server does.

/** The page address a favicon may be asked for: http(s) only. */
export function faviconTarget(raw) {
  try {
    const u = new URL(String(raw ?? ""))
    return u.protocol === "http:" || u.protocol === "https:" ? u : null
  } catch {
    return null
  }
}

/** The icons a page names (<link rel="icon"…>), absolute, largest first, then
 *  the site's /favicon.ico. */
export function faviconCandidates(pageUrl, html = "") {
  const base = faviconTarget(pageUrl)
  if (!base) return []
  const found = []
  for (const tag of String(html).match(/<link\b[^>]*>/gi) ?? []) {
    const rel = /\brel\s*=\s*["']?([^"'>]+)/i.exec(tag)?.[1]?.toLowerCase() ?? ""
    const href = /\bhref\s*=\s*["']?([^"'\s>]+)/i.exec(tag)?.[1]
    if (!href || !/(^|\s)(icon|apple-touch-icon)(\s|$)/.test(rel)) continue
    const size = Number(/\bsizes\s*=\s*["']?(\d+)/i.exec(tag)?.[1] ?? (rel.includes("apple") ? 180 : 16))
    try {
      found.push({ url: new URL(href, base).href, size })
    } catch {}
  }
  found.sort((a, b) => b.size - a.size)
  return [...new Set([...found.map(f => f.url), new URL("/favicon.ico", base).href])]
}

/** Whether an answer is an image worth serving: an image type, not too big. */
export const isIcon = (type, bytes) => /^image\//i.test(type ?? "") && bytes > 0 && bytes <= 512 * 1024
