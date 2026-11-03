// /dip: layouts kept, a dip opening the layout's folder, tabs (the one in
// front last), terminals and panes through the app's tools, the last dip's
// tabs closed, what a refused tool could not do handed to Claude, and the
// session captured as a layout.
import { expect, test } from 'claude-code/testing'

import type { DipLayout } from '../types'
import { asLayouts, brief, capture, dip, dipCommand, draftOf, layoutOf, loadDip, openDraft, saveDraft, editDraft } from '../hooks/glyphh/dip'
import { fakeHost } from './fake-host'

const API: DipLayout = {
  name: 'api',
  folder: '/code/api',
  tabs: ['http://localhost:3000/', 'https://github.com/acme/api/pulls'],
  focus: 0,
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
  expect(panes).toEqual(['terminal', 'preview'])
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

test('what a refused tool could not do goes to Claude as one prompt', async () => {
  const w = await withLayouts([API], { refuse: ['mcp__ccd_directory__change_directory', 'mcp__ccd_view__show_pane'] })
  const text = await dip(w.gh, 'api')
  expect(w.asked.length).toBe(1)
  expect(w.asked[0]!.includes('move the session to /code/api')).toBe(true)
  expect(w.asked[0]!.includes('show the terminal pane')).toBe(true)
  expect(text.includes('Claude is finishing 3 steps')).toBe(true)
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
  expect(l).toEqual({ name: 'web', folder: '/code/web', tabs: ['https://glyphh.ai/pricing'], focus: 0, panes: ['preview', 'terminal'], terminals: [{ title: 'dev', cwd: '/code/api', command: '' }], brief: '' })
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

test('capture reads full addresses, the tab in front and the open panes', async () => {
  const w = fakeHost()
  w.tools.tabs.push({ tabId: 'a', url: 'https://a.test/x?y=1', isActive: false }, { tabId: 'b', url: 'http://localhost:5173/', isActive: true })
  const l = await capture(w.gh, 'now')
  expect(l.tabs).toEqual(['https://a.test/x?y=1', 'http://localhost:5173/'])
  expect(l.focus).toBe(1)
})
