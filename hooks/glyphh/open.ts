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
  if ((await surfaceNow(gh, hint)) !== 'desktop') return false
  try {
    const r = await gh.mcp.call('Claude_Browser', 'preview_start', { url })
    if (r.isError) return false
  } catch {
    return false
  }
  await showBrowserPane(gh)
  return true
}

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
