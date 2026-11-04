// /dip: layouts kept, a dip opening the layout's folder, tabs (the one in
// front last), terminals and panes through the app's tools, the last dip's
// tabs closed, what a refused tool could not do said in the reply, and the
// session captured as a layout.
import { expect, test } from 'claude-code/testing'

import type { DipLayout } from '../types'
import { asLayouts, brief, capture, dip, dipCheck, dipCommand, draftOf, layoutOf, loadDip, openDraft, saveDraft, editDraft } from '../hooks/glyphh/dip'
import { asGrid, assign, canMergeDown, canMergeRight, cuts, emptyGrid, gridOfPanes, merge, panesOf, resizeGrid, splitCell } from '../hooks/glyphh/dipgrid'
import { fakeHost } from './fake-host'

const API: DipLayout = {
  name: 'api',
  folder: '/code/api',
  tabs: ['http://localhost:3000/', 'https://github.com/acme/api/pulls'],
  focus: 0,
  grid: gridOfPanes(['preview', 'terminal']),
  panes: ['preview', 'terminal'],
  terminals: [{ title: 'dev', cwd: '/code/api', command: 'npm run dev' }],
  brief: 'The API; tests with make test.',
}

async function withLayouts(layouts: DipLayout[], opts: { refuse?: string[] } = {}) {
  const w = fakeHost(opts)
  w.store.set('dip.layouts', layouts)
  await loadDip(w.gh)
  return w
}

test('a dip moves the folder, opens the tabs with the one in front last, the terminal and the panes', async () => {
  const w = await withLayouts([API])
  const text = await dip(w.gh, 'API')
  const tools = w.tools.calls.map(c => c.tool.replace(/^mcp__\w+?__/, ''))
  expect(tools.includes('change_directory')).toBe(true)
  const opened = w.tools.calls.filter(c => c.tool.endsWith('preview_start')).map(c => c.input.url)
  expect(opened).toEqual(['https://github.com/acme/api/pulls', 'http://localhost:3000/'])
  expect(w.tools.calls.find(c => c.tool.endsWith('run_in_terminal'))?.input).toEqual({ command: 'npm run dev', title: 'dev', cwd: '/code/api' })
  const panes = w.tools.calls.filter(c => c.tool.endsWith('show_pane')).map(c => c.input.pane)
  expect(panes).toEqual(['preview', 'terminal'])
  expect(text.startsWith('Dipped into api')).toBe(true)
  expect((await w.gh.state.dip.get()).active).toBe('api')
  expect(w.asked.length).toBe(0)
})

test('the next dip closes the tabs the last one opened', async () => {
  const web: DipLayout = { ...API, name: 'web', folder: '/code/web', tabs: ['https://glyphh.ai/'], focus: 0, terminals: [] }
  const w = await withLayouts([API, web])
  await dip(w.gh, 'api')
  await dip(w.gh, 'web')
  expect(w.tools.tabs.map(t => t.url)).toEqual(['https://glyphh.ai/'])
  // The session is in web's folder already: no move.
  expect(w.tools.calls.filter(c => c.tool.endsWith('change_directory')).length).toBe(1)
})

test('what a refused tool could not do is said, and no prompt goes to Claude', async () => {
  const w = await withLayouts([API], { refuse: ['mcp__ccd_directory__change_directory', 'mcp__ccd_view__show_pane'] })
  const text = await dip(w.gh, 'api')
  expect(w.asked.length).toBe(0)
  expect(text.includes('Could not move the session to /code/api; show the preview pane; show the terminal pane.')).toBe(true)
  expect((await w.gh.state.dip.get()).note?.isError).toBe(true)
  expect(w.files.get('/home/t/.glyphh/dip-log.txt')?.includes('mcp__ccd_view__show_pane: refused')).toBe(true)
})

test('a dip closes every pane, then opens the layout\'s down each column, a pane\'s tabs at its turn', async () => {
  // Terminal and Diff stacked in one column, the browser in the next.
  const grid = { cols: 3, rows: 2, cells: [
    { pane: 'claude' as const, col: 0, row: 0, colSpan: 1, rowSpan: 2 },
    { pane: 'terminal' as const, col: 1, row: 0, colSpan: 1, rowSpan: 1 },
    { pane: 'preview' as const, col: 2, row: 0, colSpan: 1, rowSpan: 2 },
    { pane: 'diff' as const, col: 1, row: 1, colSpan: 1, rowSpan: 1 },
  ] }
  const w = await withLayouts([{ ...API, grid, panes: ['terminal', 'preview', 'diff'] }])
  await dip(w.gh, 'api')
  const seen = w.tools.calls.map(c => `${c.tool.split('__')[2]} ${String(c.input.pane ?? '')}`.trim())
  const at = (s: string) => seen.indexOf(s)
  expect(at('close_pane preview')).toBeLessThan(at('show_pane terminal'))
  expect(at('close_pane terminal')).toBeLessThan(at('show_pane terminal'))
  expect(at('show_pane terminal')).toBeLessThan(at('show_pane diff'))
  expect(at('show_pane diff')).toBeLessThan(at('preview_start'))
  expect(at('preview_start')).toBeLessThan(at('show_pane preview'))
})

test('a layout saved in another session is found, and survives a save here', async () => {
  const w = await withLayouts([API])
  w.store.set('dip.layouts', [API, { ...API, name: 'dev' }])
  expect((await dip(w.gh, 'dev')).startsWith('Dipped into dev')).toBe(true)
  w.store.set('dip.layouts', [API, { ...API, name: 'dev' }, { ...API, name: 'web' }])
  await dipCommand(w.gh, 'save mine')
  expect(asLayouts(w.store.get('dip.layouts')).map(l => l.name)).toEqual(['api', 'dev', 'web', 'mine'])
})

test('the Files pane comes from the View menu: show_pane would need a file', async () => {
  const w = await withLayouts([{ ...API, panes: ['file'], grid: gridOfPanes(['file']), terminals: [], tabs: [], folder: '' }])
  const text = await dip(w.gh, 'api')
  expect(w.tools.calls.some(c => c.tool.endsWith('show_pane'))).toBe(false)
  expect(w.argvs.some(a => a[0] === 'osascript')).toBe(true)
  expect(text.includes('Could not')).toBe(false)
})

test('a dip answers the check for panes, tabs, the folder and a shell; a typed command is the person\'s', () => {
  for (const t of ['mcp__ccd_view__show_pane', 'mcp__Claude_Browser__preview_start', 'mcp__ccd_directory__change_directory', 'mcp__terminal__open_terminal_tab']) expect(dipCheck(t, {})).toBe('allow')
  expect(dipCheck('mcp__terminal__run_in_terminal', { command: 'make' })).toBe('ask')
  expect(dipCheck('mcp__Claude_Browser__javascript_tool', { text: 'location.href' })).toBe('allow')
  expect(dipCheck('mcp__Claude_Browser__javascript_tool', { text: 'document.cookie' })).toBe(null)
  expect(dipCheck('Bash', { command: 'ls' })).toBe(null)
})

test('an unknown name lists the layouts; a prefix finds the one it starts', async () => {
  const w = await withLayouts([API])
  expect(await dip(w.gh, 'nope')).toBe('No layout "nope". Layouts: api.')
  expect((await dip(w.gh, 'a')).startsWith('Dipped into api')).toBe(true)
})

test('/dip save keeps the session as it is; rm and off', async () => {
  const w = await withLayouts([])
  w.tools.tabs.push({ tabId: 'x', url: 'https://glyphh.ai/pricing', isActive: true })
  const said = await dipCommand(w.gh, 'save web')
  expect(said.text).toBe('Kept web: /code/web, 1 tab, 1 terminal.')
  const [l] = asLayouts(w.store.get('dip.layouts'))
  expect(l).toEqual({ name: 'web', folder: '/code/web', tabs: ['https://glyphh.ai/pricing'], focus: 0, grid: gridOfPanes(['preview', 'terminal']), panes: ['preview', 'terminal'], terminals: [{ title: 'dev', cwd: '/code/api', command: '' }], brief: '' })
  await dip(w.gh, 'web')
  expect((await dipCommand(w.gh, 'off')).text).toBe('No layout active.')
  expect((await dipCommand(w.gh, 'rm web')).text).toBe('Removed web.')
  expect(asLayouts(w.store.get('dip.layouts'))).toEqual([])
})

test('the editor writes a layout from its fields, and refuses a clash', async () => {
  const w = await withLayouts([API])
  await openDraft(w.gh, null)
  await editDraft(w.gh, d => ({ ...d, name: 'docs', folder: '/code/docs', tabs: 'glyphh.ai/docs\n* localhost:4000', terminals: 'serve | /code/docs | make serve' }))
  await saveDraft(w.gh)
  const docs = (await w.gh.state.dip.get()).layouts.find(l => l.name === 'docs')
  expect(docs?.tabs).toEqual(['https://glyphh.ai/docs', 'https://localhost:4000'])
  expect(docs?.focus).toBe(1)
  expect(docs?.terminals).toEqual([{ title: 'serve', cwd: '/code/docs', command: 'make serve' }])
  await openDraft(w.gh, 'docs')
  await editDraft(w.gh, d => ({ ...d, name: 'api' }))
  await saveDraft(w.gh)
  expect((await w.gh.state.dip.get()).note?.text).toBe('There is a layout api already.')
  expect(layoutOf(draftOf(API))).toEqual(API)
})

test('the active layout is a brief for Claude', async () => {
  const w = await withLayouts([API])
  expect(brief(await w.gh.state.dip.get())).toBe(null)
  await dip(w.gh, 'api')
  const b = brief(await w.gh.state.dip.get()) ?? ''
  expect(b.includes('"api"')).toBe(true)
  expect(b.includes('The API; tests with make test.')).toBe(true)
})

test('a layout from before grids gets one: Claude on the left, its panes beside it in order', () => {
  const { grid: _, ...old } = API
  const [l] = asLayouts([old])
  expect(l?.grid).toEqual(API.grid)
  expect(l?.panes).toEqual(['preview', 'terminal'])
  const all = asLayouts([{ ...old, panes: ['file', 'diff', 'pr', 'tasks', 'preview', 'terminal'] }])[0]!
  expect(all.panes).toEqual(['file', 'diff', 'pr', 'tasks', 'preview', 'terminal'])
  expect(cuts(all.grid) === null).toBe(false)
})

test('a broken stored grid is rebuilt from its panes', () => {
  const overlap = { cols: 2, rows: 1, cells: [{ pane: 'claude', col: 0, row: 0, colSpan: 2, rowSpan: 1 }, { pane: 'diff', col: 1, row: 0, colSpan: 1, rowSpan: 1 }] }
  expect(asGrid(overlap, ['claude', 'diff', ''])).toBe(null)
  expect(asLayouts([{ ...API, grid: overlap }])[0]?.grid).toEqual(API.grid)
})

test('cells merge, split, and a pane moves rather than doubles', () => {
  let g = assign(emptyGrid(2, 2), 0, 'claude')
  g = assign(g, 1, 'diff')
  g = assign(g, 3, 'diff')
  expect(panesOf(g)).toEqual(['diff'])
  expect(g.cells[1]?.pane).toBe('')
  expect(canMergeRight(g, 0)).toBe(true)
  const down = merge(g, 0, false)
  expect(down.grid.cells[down.cell]?.rowSpan).toBe(2)
  expect(down.grid.cells.length).toBe(3)
  // The tall cell has nothing the same height to its right.
  expect(canMergeRight(down.grid, down.cell)).toBe(false)
  const back = splitCell(down.grid, down.cell)
  expect(back.cells.length).toBe(4)
  expect(back.cells.find(c => c.col === 0 && c.row === 0)?.pane).toBe('claude')
  expect(g.cells.length).toBe(4)
})

test('a merge that would make a pinwheel is refused, so every grid can be drawn', () => {
  let g = emptyGrid(3, 3)
  const at = (col: number, row: number) => g.cells.findIndex(c => c.col === col && c.row === row)
  g = merge(g, at(0, 0), true).grid // top: columns 0-1
  g = merge(g, at(2, 0), false).grid // right: rows 0-1
  g = merge(g, at(1, 2), true).grid // bottom: columns 1-2
  expect(cuts(g) === null).toBe(false)
  expect(canMergeDown(g, at(0, 1))).toBe(false)
})

test('a resize keeps what fits and fills new room', () => {
  const g = assign(assign(emptyGrid(2, 1), 0, 'claude'), 1, 'diff')
  expect(resizeGrid(g, 1, 1).cells.map(c => c.pane)).toEqual(['claude'])
  const big = resizeGrid(g, 3, 2)
  expect(big.cells.length).toBe(6)
  expect(panesOf(big)).toEqual(['diff'])
})

test('the editor saves the grid and the panes in reading order', async () => {
  const w = await withLayouts([])
  await openDraft(w.gh, null)
  await editDraft(w.gh, d => ({ ...d, name: 'x', grid: assign(resizeGrid(d.grid, 2, 2), 2, 'diff') }))
  await saveDraft(w.gh)
  const [l] = (await w.gh.state.dip.get()).layouts
  expect(l?.panes).toEqual(['preview', 'diff'])
})

test('capture reads full addresses, the tab in front and the open panes', async () => {
  const w = fakeHost()
  w.tools.tabs.push({ tabId: 'a', url: 'https://a.test/x?y=1', isActive: false }, { tabId: 'b', url: 'http://localhost:5173/', isActive: true })
  const l = await capture(w.gh, 'now')
  expect(l.tabs).toEqual(['https://a.test/x?y=1', 'http://localhost:5173/'])
  expect(l.focus).toBe(1)
})
