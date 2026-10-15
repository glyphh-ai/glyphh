// The Claude desktop app's own panes, driven for a workspace. The app's MCP
// servers do part of it: Claude_Browser (the layout page's tab), ccd_view (a
// file in the Files pane), ccd_directory (the session's folder). The
// rest only the app's View menu does ("Show Files" opens the Files pane as a
// browser, "Show Browser" the Browser pane; each reads "Hide …" while open),
// clicked through System Events, which needs the app's Accessibility
// permission. Works on an App, closures over `$` that ./hooks.tsx hands it.
import type { McpToolResult, ProcessRunInit, ProcessRunResult } from 'claude-code'

import type { WorkspaceFile } from '../../types'

/** One state value: read it, or change it from what it is. */
export type Value<T> = { get(): Promise<T>; set(fn: (v: T) => T): Promise<void> }

export type App = {
  mcp(server: string, tool: string, args: Record<string, unknown>): Promise<McpToolResult>
  run(argv: readonly string[], init?: ProcessRunInit): Promise<ProcessRunResult>
  cwd(): Promise<string>
  isFile(path: string): Promise<boolean>
  toast(text: string): void
  /** Asks Claude, as a prompt of its own once this command is done: the way
   *  round a refused tool call. */
  ask(text: string): void
  /** Runs a slash command once the command or press in progress is done
   *  (/model, /effort: for this session only), its answer shown as a toast. */
  command(name: string, args: string): void
}

const MENU_PANES = { files: 'Files', changes: 'Changes', terminal: 'Terminal', browser: 'Browser' } as const
export type MenuPane = keyof typeof MENU_PANES

const textOf = (r: McpToolResult) => r.content.map(b => b.text ?? '').join('\n')
const short = (err: unknown, n: number) => String(err).replace(/^(Hooks)?Error: /, '').slice(0, n)

async function call(app: App, server: string, tool: string, args: Record<string, unknown>): Promise<string> {
  const r = await app.mcp(server, tool, args)
  const text = textOf(r)
  if (r.isError) throw new Error(text || `${tool} failed`)
  return text
}

async function viewMenu(app: App, script: string): Promise<string> {
  const r = await app.run([
    'osascript',
    '-e',
    `tell application "System Events" to tell process "Claude" to ${script} of menu 1 of menu bar item "View" of menu bar 1`,
  ])
  if (r.exitCode !== 0) throw new Error(r.stderr.trim() || 'osascript failed')
  return r.stdout.trim()
}

const menuItems = async (app: App) => (await viewMenu(app, 'get name of every menu item')).split(', ')
const click = (app: App, label: string) => viewMenu(app, `click menu item "${label}"`)

/** One View-menu pane shown or hidden; says what it did. */
export async function togglePane(app: App, pane: MenuPane, on: boolean): Promise<string> {
  const label = MENU_PANES[pane]
  const isOpen = (await menuItems(app)).includes(`Hide ${label}`)
  if (isOpen === on) return `${label} already ${on ? 'open' : 'closed'}`
  await click(app, `${on ? 'Show' : 'Hide'} ${label}`)
  return `${label} ${on ? 'open' : 'closed'}`
}

export const showFile = (app: App, path: string) => call(app, 'ccd_view', 'show_pane', { pane: 'file', path })

/** A page in the Browser pane, in a new tab. */
export async function openPage(app: App, url: string): Promise<void> {
  await togglePane(app, 'browser', true)
  await openTab(app, url)
}

/** A file by path (absolute or from the session's folder), or by name under it. */
export async function findFile(app: App, name: string): Promise<string[]> {
  const cwd = await app.cwd()
  const direct = name.startsWith('/') ? name : `${cwd}/${name}`
  if (await app.isFile(direct)) return [direct]
  const base = name.split('/').pop()!
  const r = await app
    .run(['find', cwd, '-type', 'f', '-name', base, '-not', '-path', '*/node_modules/*', '-not', '-path', '*/.git/*'], { timeoutMs: 10_000 })
    .catch(() => null)
  const hits = (r?.stdout ?? '').split('\n').filter(Boolean)
  return name.includes('/') ? hits.filter(h => h.endsWith(`/${name}`)) : hits
}

/** The app panes a workspace's cells point at, in grid order, and the
 *  Browser pane last (in front) when it shows pages. */
export function panesOf(ws: WorkspaceFile): MenuPane[] {
  const order = [...ws.cells].sort((a, b) => a.col - b.col || a.row - b.row)
  const panes: MenuPane[] = []
  for (const c of order) if (c.panel !== 'browser' && !panes.includes(c.panel)) panes.push(c.panel)
  if (ws.cells.some(c => c.panel === 'browser')) panes.push('browser')
  return panes
}

/** The app's panes for a workspace: close what it does not use, then open
 *  what it does, in order. Says, per pane, how it went. */
async function applyPanes(app: App, ws: WorkspaceFile): Promise<string[]> {
  const want = panesOf(ws)
  const report: string[] = []
  let items: string[]
  try {
    items = await menuItems(app)
  } catch (err) {
    return [`panes ✗ the View menu: ${short(err, 120)}`]
  }
  const press = async (label: string) => {
    try {
      await click(app, label)
      return true
    } catch (err) {
      report.push(`${label} ✗ ${short(err, 80)}`)
      return false
    }
  }
  for (const [pane, label] of Object.entries(MENU_PANES)) {
    if (!want.includes(pane as MenuPane) && items.includes(`Hide ${label}`)) await press(`Hide ${label}`)
  }
  for (const pane of want) {
    const label = MENU_PANES[pane]
    if (items.includes(`Hide ${label}`) || (await press(`Show ${label}`))) report.push(`${label} ✓`)
  }
  return report
}

/** A page in a new tab of the Browser pane: the tab's id, when it says. */
export async function openTab(app: App, url: string): Promise<string | undefined> {
  const text = await call(app, 'Claude_Browser', 'preview_start', { url })
  return /"tabId":\s*"([^"]+)"/.exec(text)?.[1]
}

export async function closeTab(app: App, tabId: string): Promise<void> {
  await app.mcp('Claude_Browser', 'tabs_close', { tabId }).catch(() => undefined)
}

async function moveFolder(app: App, folder: string | null): Promise<void> {
  if (!folder || folder === (await app.cwd())) return
  try {
    const r = await app.mcp('ccd_directory', 'change_directory', { path: folder })
    app.toast(r.isError ? `Folder not moved: ${textOf(r).slice(0, 120)}` : `The session moves to ${folder}`)
  } catch (err) {
    app.toast(`Folder not moved: ${short(err, 120)}`)
  }
}

/** The app's side of a switch: the panes, the session's model and effort
 *  (when the workspace names them), then the folder, which may wait on the
 *  person's approval, so nothing waits on it. */
export async function applyWorkspace(app: App, ws: WorkspaceFile): Promise<string> {
  const report = await applyPanes(app, ws)
  if (ws.model) {
    app.command('model', ws.model)
    report.push(`model ${ws.model}`)
  }
  if (ws.effort) {
    app.command('effort', ws.effort)
    report.push(`effort ${ws.effort}`)
  }
  void moveFolder(app, ws.folder)
  return report.join(' · ')
}
