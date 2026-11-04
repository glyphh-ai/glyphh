// /dip <layout>: bounces the session between workspaces. A layout is the
// session's folder, the browser pane's tabs (one in front), the side panes,
// the terminal tabs and a brief Claude reads while it is active; dipping
// calls the desktop app's own tools for each, the mod doing all of it with no
// turn of Claude's: dipCheck answers the permission check for the calls a dip
// makes, and what could not be done is said in the reply. Layouts live in the
// store across sessions; the Dip pane writes them.
import type { DipCellPane, DipDraft, DipGrid, DipLayout, DipPane, DipTerminal, DipView } from '../../types'
import { arranged, asGrid, assign, emptyGrid, gridOfPanes, gridOfRects, moves, openOrder, panesOf, peels, type Rect } from './dipgrid'
import type { Host } from './host'

export const PANES: { id: DipPane; label: string }[] = [
  { id: 'preview', label: 'Browser' },
  { id: 'terminal', label: 'Terminal' },
  { id: 'file', label: 'Files' },
  { id: 'diff', label: 'Diff' },
  { id: 'pr', label: 'PR' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'plan', label: 'Plan' },
  { id: 'artifact', label: 'Artifacts' },
]

/** What a cell can hold, in the order the editor offers it. */
export const FILLS: { id: DipCellPane; label: string }[] = [{ id: 'claude', label: 'Claude' }, ...PANES, { id: '', label: 'Empty' }]

export const FIRST_DIP: DipView = { layouts: [], active: null, draft: null, note: null }

const LAYOUTS = 'dip.layouts'
const ACTIVE = 'dip.active'
/** The browser tabs the last dip opened, closed by the next. */
const OPENED = 'dip.opened'

export const USAGE_DIP = '/dip [<layout> | save <name> | rm <name> | off]'

const T = {
  dir: 'mcp__ccd_directory__change_directory',
  pane: 'mcp__ccd_view__show_pane',
  layout: 'mcp__ccd_view__get_layout',
  open: 'mcp__Claude_Browser__preview_start',
  tabs: 'mcp__Claude_Browser__tabs_context',
  close: 'mcp__Claude_Browser__tabs_close',
  js: 'mcp__Claude_Browser__javascript_tool',
  shell: 'mcp__terminal__open_terminal_tab',
  run: 'mcp__terminal__run_in_terminal',
  shells: 'mcp__terminal__list_terminal_tabs',
  closePane: 'mcp__ccd_view__close_pane',
}

/** Layouts from the store into the pane's state: at session start, and before each use, since another session may
 *  have saved since and writing an old list back would lose its layout. */
export async function loadDip(gh: Host) {
  const layouts = asLayouts(await gh.store.get(LAYOUTS).catch(() => undefined))
  const active = await gh.store.get(ACTIVE).catch(() => undefined)
  // A draft from before grids is dropped: the editor draws a draft's grid.
  await gh.state.dip.set(v => ({ ...v, layouts, draft: v.draft?.grid ? v.draft : null, active: typeof active === 'string' && layouts.some(l => l.name === active) ? active : null }))
}

const say = (gh: Host, text: string, isError = false) => gh.state.dip.set(v => ({ ...v, note: { text, isError } }))

async function keep(gh: Host, layouts: DipLayout[]) {
  await gh.store.set(LAYOUTS, layouts)
  await gh.state.dip.set(v => ({ ...v, layouts }))
}

async function setActive(gh: Host, name: string | null) {
  await gh.store.set(ACTIVE, name)
  await gh.state.dip.set(v => ({ ...v, active: name }))
}

/** A name as typed: exact, then any case, then the one layout it starts. */
export function findLayout(layouts: DipLayout[], typed: string): DipLayout | undefined {
  const t = typed.trim().toLowerCase()
  const exact = layouts.find(l => l.name === typed.trim()) ?? layouts.find(l => l.name.toLowerCase() === t)
  if (exact) return exact
  const starts = layouts.filter(l => l.name.toLowerCase().startsWith(t))
  return starts.length === 1 ? starts[0] : undefined
}

/** The JSON a tool answered: the whole text, or its first JSON value with words after it (the browser's
 *  tabs_context adds a sentence). */
function jsonIn(text: string): unknown {
  const parse = (s: string) => {
    try {
      return { v: JSON.parse(s) as unknown }
    } catch {
      return undefined
    }
  }
  const whole = parse(text)
  if (whole) return whole.v
  const start = text.search(/[[{]/)
  if (start < 0) return undefined
  for (let end = text.indexOf(text[start] === '{' ? '}' : ']', start); end > 0; end = text.indexOf(text[start] === '{' ? '}' : ']', end + 1)) {
    const part = parse(text.slice(start, end + 1))
    if (part) return part.v
  }
  return undefined
}

type Tab = { tabId: string; isActive: boolean; origin: string }

async function browserTabs(gh: Host): Promise<Tab[]> {
  const r = await gh.tool.call(T.tabs, {})
  const tabs = (jsonIn(r.text) as { tabs?: unknown } | undefined)?.tabs
  return Array.isArray(tabs) ? tabs.filter((t): t is Tab => !!t && typeof (t as Tab).tabId === 'string') : []
}

/** /dip <name>: the layout, made the session's workspace. */
export async function dip(gh: Host, typed: string): Promise<string> {
  await loadDip(gh)
  const { layouts } = await gh.state.dip.get()
  const l = findLayout(layouts, typed)
  if (!l) {
    const names = layouts.map(x => x.name).join(', ')
    return names ? `No layout "${typed.trim()}". Layouts: ${names}.` : 'No layouts yet: /dip opens the Dip pane to make one, or /dip save <name> keeps this one.'
  }
  const left: string[] = []
  const refused: string[] = []
  const step = async (tool: string, input: Record<string, unknown>, words: string) => {
    const r = await gh.tool.call(tool, input)
    if (!r.ok) {
      left.push(words)
      refused.push(`${tool}: ${r.text.slice(0, 300)}`)
    }
    return r
  }

  if (l.folder && l.folder !== (await gh.cwd().catch(() => ''))) {
    await step(T.dir, { path: l.folder }, `move the session to ${l.folder}`)
  }

  // The app places a pane by when it opens (the first beside Claude, the second under it, the third in a new
  // column), so every pane closes and the layout's open in order. A tab or a terminal tab opens its pane, so each
  // waits for that pane's turn.
  const open = jsonIn((await gh.tool.call(T.layout, {})).text) as { open_panes?: unknown } | undefined
  for (const pane of asStrings(open?.open_panes)) await gh.tool.call(T.closePane, { pane })

  // The tabs the last dip opened go; this layout's open, the one in front last.
  const stale = asStrings(await gh.store.get(OPENED).catch(() => undefined))
  for (const tabId of stale) await gh.tool.call(T.close, { tabId })
  const openTabs = async () => {
    const before = new Set((await browserTabs(gh)).map(t => t.tabId))
    const order = l.tabs.map((url, i) => ({ url, i })).sort((a, b) => Number(a.i === l.focus) - Number(b.i === l.focus))
    for (const { url } of order) await step(T.open, { url }, `open ${url}`)
    await gh.store.set(OPENED, (await browserTabs(gh)).map(t => t.tabId).filter(id => !before.has(id)))
  }
  const openTerminals = async () => {
    for (const t of l.terminals) {
      const at = t.cwd ? { cwd: t.cwd } : {}
      const title = t.title || 'shell'
      if (t.command) await step(T.run, { command: t.command, title, ...at }, `run \`${t.command}\` in a terminal tab titled "${title}"${t.cwd ? ` in ${t.cwd}` : ''}`)
      else await step(T.shell, { title, ...at }, `open a terminal tab titled "${title}"${t.cwd ? ` in ${t.cwd}` : ''}`)
    }
  }

  const panes = openOrder(l.grid)
  for (const pane of panes) {
    if (pane === 'preview') {
      if (!l.tabs.length) continue
      await openTabs()
    } else if (pane === 'terminal') {
      await openTerminals()
    }
    if (pane === 'file') {
      if (!(await showFiles(gh))) left.push('show the Files pane')
      continue
    }
    await step(T.pane, { pane }, `show the ${pane} pane`)
  }
  if (!panes.includes('preview')) await openTabs()
  if (!panes.includes('terminal')) await openTerminals()

  const shown = panes.filter(p => p !== 'preview' || l.tabs.length)
  const off = peels(l.grid, shown)
  if (!off) left.push('arrange this grid: the app can only build one tile at a time from the outside in')
  else if (off.length) {
    const placed = await runArrange(gh, moves(off))
    if (placed.error) left.push(placed.error)
    else if (!arranged(l.grid, placed.tiles)) left.push('arrange the panes as the grid says')
  }

  await setActive(gh, l.name)
  const what = [l.folder && l.folder.split('/').pop(), l.tabs.length && `${l.tabs.length} tab${l.tabs.length > 1 ? 's' : ''}`, l.terminals.length && `${l.terminals.length} terminal${l.terminals.length > 1 ? 's' : ''}`, ...l.panes.map(p => PANES.find(x => x.id === p)?.label)].filter(Boolean)
  const done = `Dipped into ${l.name}${what.length ? `: ${what.join(', ')}` : ''}.`
  if (!left.length) {
    await say(gh, done)
    return done
  }
  // Why each step was refused, for the next look; the last dip's alone.
  const home = await gh.env.home().catch(() => undefined)
  if (home) await gh.fs.write(`${home}/.glyphh/dip-log.txt`, `${refused.join('\n')}\n`).catch(() => undefined)
  const text = `${done} Could not ${left.join('; ')}.`
  await say(gh, text, true)
  return text
}

/** hooks/dip_arrange.py, which works the app's Move handles and says where every tile is. No moves just measures. */
async function runArrange(gh: Host, ops: { tile: string; keys: string[] }[]): Promise<{ tiles: Record<string, Rect>; error?: string }> {
  try {
    const r = await gh.process.run(['python3', `${gh.pluginRoot}/hooks/dip_arrange.py`, JSON.stringify({ ops })])
    const said = jsonIn(r.stdout) as { ok?: boolean; error?: string; tiles?: Record<string, Rect> } | undefined
    if (said?.ok) return { tiles: said.tiles ?? {} }
    const why = said?.error === 'accessibility' ? 'arrange the panes: allow Claude under System Settings, Privacy & Security, Accessibility' : `arrange the panes (${said?.error ?? 'no answer'})`
    return { tiles: said?.tiles ?? {}, error: why }
  } catch (err) {
    return { tiles: {}, error: `arrange the panes (${String(err).slice(0, 100)})` }
  }
}

/** The Files pane: show_pane opens one file and needs its path, so the whole pane comes from the app's View menu
 *  ("Show Files"), as open.ts does for the browser. The item reads Hide Files when the pane is open. */
async function showFiles(gh: Host): Promise<boolean> {
  const menu = (script: string) =>
    gh.process.run(['osascript', '-e', `tell application "System Events" to tell process "Claude" to ${script} of menu 1 of menu bar item "View" of menu bar 1`])
  try {
    const items = await menu('get name of every menu item')
    if (items.exitCode !== 0) return false
    if (!items.stdout.includes('Show Files')) return true
    return (await menu('click menu item "Show Files"')).exitCode === 0
  } catch {
    return false
  }
}

/** The app's tools a dip calls and what they do, answered at the permission check for the mod's own calls (a
 *  person's /dip or Dip press is the only way they start). A dip runs no turn, so auto mode's classifier has no
 *  request to read and refuses them all. Panes, tabs, the layout's folder and a bare shell go ahead; a command typed
 *  into a terminal is put to the person, line and all; anything else takes the check beneath. */
export function dipCheck(tool: string, input: unknown): 'allow' | 'ask' | null {
  if ([T.dir, T.pane, T.closePane, T.layout, T.open, T.tabs, T.close, T.shell, T.shells].includes(tool)) return 'allow'
  if (tool === T.js) return (input as { text?: unknown } | null)?.text === 'location.href' ? 'allow' : null
  return tool === T.run ? 'ask' : null
}

/** What the session looks like now, as a layout: the folder, the browser tabs (full addresses where the page
 *  answers), the open panes and the terminal tabs. */
export async function capture(gh: Host, name: string, brief = ''): Promise<DipLayout> {
  const folder = await gh.cwd().catch(() => '')
  const tabs = await browserTabs(gh)
  const urls: string[] = []
  let focus = -1
  for (const t of tabs) {
    const r = await gh.tool.call(T.js, { action: 'javascript_exec', text: 'location.href', tabId: t.tabId })
    const href = r.ok ? String(jsonIn(r.text) ?? r.text).match(/https?:\/\/\S+?(?="|$|\s)/)?.[0] : undefined
    const url = href ?? t.origin
    if (!/^https?:\/\//.test(url)) continue
    if (t.isActive) focus = urls.length
    urls.push(url)
  }
  const layout = await gh.tool.call(T.layout, {})
  const openPanes = layout.ok ? JSON.stringify(jsonIn(layout.text) ?? layout.text) : ''
  const panes = PANES.map(p => p.id).filter(p => new RegExp(`"${p}"`).test(openPanes))
  const shells = jsonIn((await gh.tool.call(T.shells, {})).text)
  const list = Array.isArray(shells) ? shells : Array.isArray((shells as { tabs?: unknown })?.tabs) ? (shells as { tabs: unknown[] }).tabs : []
  const terminals: DipTerminal[] = list.map(t => {
    const s = (t ?? {}) as Record<string, unknown>
    return { title: String(s.title ?? 'shell'), cwd: String(s.cwd ?? s.directory ?? ''), command: '' }
  })
  // The panes as they sit now, dragged or not; where they can't be measured, Claude with the panes beside it.
  const measured = gridOfRects((await runArrange(gh, [])).tiles, FILLS.map(f => f.id))
  const grid = measured ?? gridOfPanes(panes)
  return { name, folder, tabs: urls, focus, grid, panes: panesOf(grid), terminals, brief }
}

/** /dip save <name>: the session as it is, kept as that layout (its brief kept when it existed). */
export async function saveCurrent(gh: Host, name: string): Promise<string> {
  const n = name.trim()
  if (!n) return `Name it: ${USAGE_DIP}`
  const { layouts } = await gh.state.dip.get()
  const old = layouts.find(l => l.name === n)
  const l = await capture(gh, n, old?.brief ?? '')
  await keep(gh, old ? layouts.map(x => (x.name === n ? l : x)) : [...layouts, l])
  const text = `Kept ${n}: ${l.folder || 'no folder'}, ${l.tabs.length} tab${l.tabs.length === 1 ? '' : 's'}, ${l.terminals.length} terminal${l.terminals.length === 1 ? '' : 's'}.`
  await say(gh, text)
  return text
}

export async function removeLayout(gh: Host, name: string): Promise<string> {
  await loadDip(gh)
  const { layouts, active } = await gh.state.dip.get()
  const l = findLayout(layouts, name)
  if (!l) return `No layout "${name.trim()}".`
  await keep(gh, layouts.filter(x => x !== l))
  if (active === l.name) await setActive(gh, null)
  await say(gh, `Removed ${l.name}.`)
  return `Removed ${l.name}.`
}

/** /dip [args]: the pane with no args, else dip, save, rm or off. */
export async function dipCommand(gh: Host, args: string): Promise<{ text: string }> {
  await loadDip(gh)
  const a = args.trim()
  if (!a) {
    const placed = await gh.openDip()
    const { layouts, active } = await gh.state.dip.get()
    const line = layouts.length ? `Layouts: ${layouts.map(l => (l.name === active ? `${l.name} (active)` : l.name)).join(', ')}.` : 'No layouts yet.'
    return { text: placed ? line : `${line} ${USAGE_DIP}` }
  }
  const [verb, ...rest] = a.split(/\s+/)
  const tail = rest.join(' ')
  if (verb === 'save') return { text: await saveCurrent(gh, tail) }
  if (verb === 'rm' || verb === 'remove' || verb === 'delete') return { text: await removeLayout(gh, tail) }
  if (verb === 'off' && !findLayout((await gh.state.dip.get()).layouts, 'off')) {
    await setActive(gh, null)
    return { text: 'No layout active.' }
  }
  return { text: await dip(gh, a) }
}

/** What Claude reads while a layout is active: its name, folder and brief. */
export function brief(view: DipView): string | null {
  const l = view.layouts.find(x => x.name === view.active)
  if (!l) return null
  const lines = [`The person's active workspace (/dip) is "${l.name}".`]
  if (l.folder) lines.push(`Its folder: ${l.folder}.`)
  if (l.tabs.length) lines.push(`Its browser tabs: ${l.tabs.join(', ')}.`)
  if (l.brief.trim()) lines.push(l.brief.trim())
  return lines.join('\n')
}

// The pane's editor.

/** A new layout starts as Claude beside the browser. */
const NEW_GRID: DipGrid = assign(assign(emptyGrid(2, 1), 0, 'claude'), 1, 'preview')

export const draftOf = (l: DipLayout | null): DipDraft =>
  l
    ? {
        original: l.name,
        name: l.name,
        folder: l.folder,
        tabs: l.tabs.map((u, i) => (i === l.focus ? `* ${u}` : u)).join('\n'),
        grid: l.grid,
        cell: 0,
        terminals: l.terminals.map(t => [t.title, t.cwd, t.command].join(' | ')).join('\n'),
        brief: l.brief,
      }
    : { original: null, name: '', folder: '', tabs: '', grid: NEW_GRID, cell: 1, terminals: '', brief: '' }

export function layoutOf(d: DipDraft): DipLayout {
  const lines = d.tabs.split('\n').map(s => s.trim()).filter(Boolean)
  const focus = lines.findIndex(s => s.startsWith('*'))
  const tabs = lines.map(s => s.replace(/^\*\s*/, '')).map(s => (/^[a-z]+:\/\//i.test(s) ? s : `https://${s}`))
  const terminals = d.terminals
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean)
    .map(s => {
      const [title = '', cwd = '', ...command] = s.split('|').map(x => x.trim())
      return { title: title || 'shell', cwd, command: command.join(' | ') }
    })
  return { name: d.name.trim(), folder: d.folder.trim(), tabs, focus, grid: d.grid, panes: panesOf(d.grid), terminals, brief: d.brief }
}

export const editDraft = (gh: Host, fn: (d: DipDraft) => DipDraft) => gh.state.dip.set(v => (v.draft ? { ...v, draft: fn(v.draft) } : v))

export async function openDraft(gh: Host, name: string | null) {
  await loadDip(gh)
  const { layouts } = await gh.state.dip.get()
  const l = name ? layouts.find(x => x.name === name) ?? null : null
  await gh.state.dip.set(v => ({ ...v, draft: draftOf(l), note: null }))
}

/** A new draft from the session as it is now. */
export async function draftFromNow(gh: Host) {
  const l = await capture(gh, '')
  await gh.state.dip.set(v => ({ ...v, draft: { ...draftOf(l), original: null }, note: null }))
}

export async function saveDraft(gh: Host) {
  await loadDip(gh)
  const { draft, layouts, active } = await gh.state.dip.get()
  if (!draft) return
  const l = layoutOf(draft)
  if (!l.name) return say(gh, 'Give the layout a name.', true)
  if (/\s/.test(l.name)) return say(gh, 'A layout name is one word (/dip <name>).', true)
  if (['save', 'rm', 'remove', 'delete', 'off'].includes(l.name.toLowerCase())) return say(gh, `"${l.name}" is one of /dip's own words.`, true)
  if (l.name !== draft.original && layouts.some(x => x.name === l.name)) return say(gh, `There is a layout ${l.name} already.`, true)
  const next = draft.original && layouts.some(x => x.name === draft.original) ? layouts.map(x => (x.name === draft.original ? l : x)) : [...layouts, l]
  await keep(gh, next)
  if (active && active === draft.original) await setActive(gh, l.name)
  await gh.state.dip.set(v => ({ ...v, draft: null, note: { text: `Saved ${l.name}: /dip ${l.name}`, isError: false } }))
}

export const closeDraft = (gh: Host) => gh.state.dip.set(v => ({ ...v, draft: null }))

function asStrings(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}

/** Layouts as the store holds them, any older or broken entry made whole or left out. */
export function asLayouts(v: unknown): DipLayout[] {
  if (!Array.isArray(v)) return []
  return v.flatMap(x => {
    const o = (x ?? {}) as Record<string, unknown>
    if (typeof o.name !== 'string' || !o.name) return []
    const terms = Array.isArray(o.terminals) ? o.terminals : []
    const grid = asGrid(o.grid, FILLS.map(f => f.id)) ?? gridOfPanes(asStrings(o.panes).filter((p): p is DipPane => PANES.some(x => x.id === p)))
    return [
      {
        name: o.name,
        folder: typeof o.folder === 'string' ? o.folder : '',
        tabs: asStrings(o.tabs),
        focus: typeof o.focus === 'number' ? o.focus : -1,
        grid,
        panes: panesOf(grid),
        terminals: terms.map(t => {
          const s = (t ?? {}) as Record<string, unknown>
          return { title: String(s.title ?? 'shell'), cwd: String(s.cwd ?? ''), command: String(s.command ?? '') }
        }),
        brief: typeof o.brief === 'string' ? o.brief : '',
      },
    ]
  })
}
