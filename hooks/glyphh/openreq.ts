// Pages the sign-in card asks to open: the card's MCP server cannot reach
// Claude's browser pane, so it leaves ~/.glyphh/open-request.json and the mod,
// which can, opens it there (within a second) and removes the file. Only the
// Glyphh sign-in page, and only a request under a minute old.
import { glyphhPath, readJson, removeFile } from './home'
import type { Host } from './host'
import { lastOpenError, openUrl, surfaceNow } from './open'

const SIGN_IN_PAGE = /^https?:\/\/[^\s?#]+\/v1\/device\?code=[A-Z0-9-]+$/
let watching = false

async function tick(gh: Host) {
  const path = await glyphhPath(gh, 'open-request.json')
  const req = await readJson<{ url?: string; at?: number }>(path, gh)
  if (path && req) {
    await removeFile(gh, path).catch(() => undefined)
    const fresh = Date.now() - (req.at ?? 0) < 60_000
    if (fresh && typeof req.url === 'string' && SIGN_IN_PAGE.test(req.url)) {
      const surface = await surfaceNow(gh)
      const opened = await openUrl(gh, req.url)
      const log = await glyphhPath(gh, 'open-log.txt')
      if (log) await gh.fs.write(log, `${new Date().toISOString()} surface=${surface} opened=${opened}${opened ? '' : ` error=${lastOpenError}`}\n`).catch(() => undefined)
    }
  }
  gh.clock.after(1000, () => void tick(gh))
}

export function watchOpenRequests(gh: Host) {
  if (watching) return
  watching = true
  void tick(gh)
}
