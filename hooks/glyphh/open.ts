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
    return !r.isError
  } catch {
    return false
  }
}
