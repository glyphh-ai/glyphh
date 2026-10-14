// Opening a page for the person: on the desktop, a tab of Claude's browser
// pane (the Claude_Browser MCP server's preview_start); in a terminal there is
// no pane, so the panel and the command print the link instead.
import type { RenderSurface } from 'claude-code'
import type { Host } from './host'

export async function surfaceNow(gh: Host, hint?: RenderSurface): Promise<RenderSurface | null> {
  if (hint) return hint
  return gh.surface().catch(() => null)
}

/** Opens `url` in the browser pane on the desktop; false where it could not
 *  (a terminal, the tool refused, no pane): the caller shows the link. */
export async function openUrl(gh: Host, url: string, hint?: RenderSurface): Promise<boolean> {
  const surface = await surfaceNow(gh, hint)
  let ok = surface === 'desktop' && (await openInPane(gh, url))
  if (!ok && surface === 'desktop') {
    // As the grid's layoutToPane does: when auto mode refuses the mod's own
    // call, Claude is asked to open it (a turn, slower, but it gets there).
    ok = await gh.ask(`Open this in the browser pane, in the tab already on ${new URL(url).host} if one is open (navigate that tab, as the grid's showInPane reuses a tab on the same site; no new tab): ${url}`).then(() => true, () => false)
  }
  const dir = await gh.env.home().catch(() => '')
  if (dir) await gh.fs.write(`${dir}/.glyphh/open-log.txt`, `${new Date().toISOString()} surface=${surface} opened=${ok}${ok ? '' : ` error=${lastOpenError}`}\n`).catch(() => undefined)
  return ok
}

async function openInPane(gh: Host, url: string): Promise<boolean> {
  // The pane first (it may be closed), then the page in it; one retry, since
  // a pane that was closed can refuse the first call.
  await showBrowserPane(gh)
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const r = await gh.mcp.call('Claude_Browser', 'preview_start', { url })
      if (!r.isError) return true
      lastOpenError = r.content.map(b => ('text' in b ? String(b.text) : '')).join(' ').slice(0, 300)
    } catch (err) {
      lastOpenError = String(err).slice(0, 300)
    }
  }
  return false
}

/** Why the last open failed, for the log. */
export let lastOpenError = ''

/** The tab opens in the browser pane, which may be hidden: no tool shows it, so,
 *  as the grid does (togglePane), the app's View menu does ("Show Browser"),
 *  clicked through System Events. Best effort: a refusal leaves the tab there. */
async function showBrowserPane(gh: Host) {
  const menu = (script: string) =>
    gh.process.run([
      'osascript', '-e',
      `tell application "System Events" to tell process "Claude" to ${script} of menu 1 of menu bar item "View" of menu bar 1`,
    ])
  try {
    const items = await menu('get name of every menu item')
    if (items.exitCode === 0 && items.stdout.includes('Show Browser')) await menu('click menu item "Show Browser"')
  } catch {
    // no Accessibility permission, or another language's menu
  }
}
