import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import * as W from '../hooks/glyphh/wsactions'
import { migrateAndLoad, readAll, saveSizes } from '../hooks/glyphh/wsfiles'
import { HOME, fakeHost } from './fake-host'

const DIR = `${HOME}/.glyphh/workspaces`

async function ready() {
  const w = fakeHost()
  await migrateAndLoad(w.gh)
  await signedIn(w.gh, 'i1', w.server.TOKEN)
  return w
}

test('first run: the built-in layouts become workspace files, in order, /dip still works on them', async () => {
  const w = fakeHost()
  await w.gh.state.layouts.set(all => all.map(l => (l.name === 'IDE' ? { ...l, colWidths: [0.3, 0.4, 0.3] } : l)))
  const entries = await migrateAndLoad(w.gh)
  expect(entries?.map(e => e.slug)).toEqual(['comms', 'browse-file', 'two-browsers', 'ide', 'files'])
  const comms = JSON.parse(w.files.get(`${DIR}/comms.json`)!)
  expect(comms).toMatchObject({ name: 'Comms', cols: 2, rows: 2, desktop_panes: ['browser'], folder: '/Users/timmetim/development/yo', model: null })
  expect(comms.tabs.map((t: { url: string }) => t.url)).toEqual(['https://mail.google.com', 'https://app.slack.com', 'https://calendar.google.com'])
  expect(comms.cells[0]).toEqual({ panel: 'browser', col: 0, row: 0, row_span: 2, tab: 0 })
  expect(JSON.parse(w.files.get(`${DIR}/ide.json`)!).col_widths).toEqual([0.3, 0.4, 0.3]) // saved sizes kept
  expect((await w.gh.state.layouts.get()).map(l => l.name)).toEqual(['Comms', 'Browse + file', 'Two browsers', 'IDE', 'Files'])
  expect((await w.gh.state.layouts.get())[0]?.cells[1]?.url).toBe('https://app.slack.com')

  w.files.delete(`${DIR}/files.json`) // a second start reads, never re-migrates
  await migrateAndLoad(w.gh)
  expect((await w.gh.state.layouts.get()).map(l => l.name)).not.toContain('Files')
})

test('dragged sizes go to the workspace file', async () => {
  const w = fakeHost()
  await migrateAndLoad(w.gh)
  const all = await w.gh.state.layouts.get()
  await saveSizes(w.gh, all.map(l => (l.name === 'Browse + file' ? { ...l, colWidths: [0.7, 0.3] } : l)))
  expect(JSON.parse(w.files.get(`${DIR}/browse-file.json`)!).col_widths).toEqual([0.7, 0.3])
})

test('create: the server first; past the limit nothing is made and the limit is said', async () => {
  const w = await ready()
  await W.createWorkspace(w.gh, 'Research')
  expect(w.s.workspaces).toEqual(['Comms', 'Research'])
  expect(JSON.parse(w.files.get(`${DIR}/research.json`)!)).toMatchObject({ name: 'Research', cols: 1, rows: 1 })
  expect(await w.gh.state.selected.get()).toBe('Research')
  expect((await w.gh.state.layouts.get()).at(-1)?.name).toBe('Research')

  await W.createWorkspace(w.gh, 'Third')
  expect(await w.gh.state.note.get()).toEqual({
    text: 'Upgrade to add more. (2 of 2 workspaces used) (trace tr-1)',
    isError: true,
  })
  expect(w.files.has(`${DIR}/third.json`)).toBe(false)
  await W.createWorkspace(w.gh, 'Comms')
  expect(await w.note()).toBe('A workspace "Comms" is already on this machine.')
})

test('edit: model, folder, permission mode and effort go to the local file only', async () => {
  const w = await ready()
  const before = w.s.calls.length
  await W.setField(w.gh, 'Comms', 'model', 'opus')
  await W.setField(w.gh, 'Comms', 'permission_mode', 'plan')
  await W.setField(w.gh, 'Comms', 'effort', 'high')
  await W.setField(w.gh, 'Comms', 'folder', '/Users/me/code')
  expect(JSON.parse(w.files.get(`${DIR}/comms.json`)!)).toMatchObject({ model: 'opus', permission_mode: 'plan', effort: 'high', folder: '/Users/me/code' })
  expect(w.s.calls.length).toBe(before)
  await W.setField(w.gh, 'Comms', 'folder', 'relative')
  expect(await w.note()).toBe('The folder must be an absolute path.')
  await W.setField(w.gh, 'Comms', 'model', '')
  expect(JSON.parse(w.files.get(`${DIR}/comms.json`)!).model).toBeNull()
})

test('rename and delete: server name and local file together; a local-only name is fine', async () => {
  const w = await ready()
  await w.gh.state.active.set(() => 'Comms')
  await W.renameWorkspace(w.gh, 'Comms', 'Mail')
  expect(w.s.workspaces).toEqual(['Mail'])
  expect(w.files.has(`${DIR}/comms.json`)).toBe(false)
  expect(JSON.parse(w.files.get(`${DIR}/mail.json`)!).name).toBe('Mail')
  expect(await w.gh.state.active.get()).toBe('Mail')
  expect((await readAll(w.gh))?.[0]?.slug).toBe('mail') // keeps its place

  await W.renameWorkspace(w.gh, 'IDE', 'Code') // never registered: 404 tolerated
  expect(w.files.has(`${DIR}/code.json`)).toBe(true)
  await W.deleteWorkspace(w.gh, 'Mail')
  expect(w.s.workspaces).toEqual([])
  expect(w.files.has(`${DIR}/mail.json`)).toBe(false)
  expect((await w.gh.state.layouts.get()).map(l => l.name)).not.toContain('Mail')
  await W.registerWorkspace(w.gh, 'Code')
  expect(w.s.workspaces).toEqual(['Code'])
})
