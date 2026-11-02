// The Apps section's actions against the fake catalogue, and /glyphh publish
// against the fake local rrotor.
import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import * as A from '../hooks/glyphh/actions'
import * as R from '../hooks/glyphh/apps'
import { glyphhCommand } from '../hooks/glyphh/command'
import { HOME, fakeHost } from './fake-host'
import { RROTOR_TOKEN, app } from './fake-server'

async function signedInHost(surface: 'desktop' | 'terminal' = 'desktop') {
  const w = fakeHost({ surface })
  await signedIn(w.gh, 'i1', w.server.TOKEN)
  return w
}

const titles = async (w: ReturnType<typeof fakeHost>) => ((await w.gh.state.lists.get()).apps ?? []).map(a => a.title)
const last = (w: ReturnType<typeof fakeHost>) => w.s.calls.at(-1)!
const view = (w: ReturnType<typeof fakeHost>) => w.gh.state.apps.get()
const published = (w: ReturnType<typeof fakeHost>, n: number) => w.s.published[n]!.body as Record<string, unknown>

test('apps: opening the section lists the published ones, 24 a page, by the state asked, every type', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'apps')
  expect(await titles(w)).toEqual(['App 1', 'App 2', 'App 3'])
  expect(last(w)).toMatchObject({ path: '/v1/apps', query: { page: '1', per_page: '24', state: 'approved' } })
  expect(last(w).query.type).toBeUndefined()
  expect(await view(w)).toMatchObject({ total: 3, page: 1, state: 'approved', type: '' })
  expect(R.pageLine(await view(w), 3)).toBe('1–3 of 3')
})

test('apps: search narrows by title, description or name and goes back to page 1', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'apps')
  await R.turnPage(w.gh, 1)
  await R.searchApps(w.gh, ' app-2 ')
  expect(last(w).query).toMatchObject({ q: 'app-2', page: '1' })
  expect(await titles(w)).toEqual(['App 2'])
  await R.searchApps(w.gh, 'nothing-like-it')
  expect(await titles(w)).toEqual([])
  expect(R.pageLine(await view(w), 0)).toBe('Nothing here.')
})

test('apps: the type filter cycles All types → Pages → … → Designs → All types, from page 1', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'apps')
  expect(R.typeLabel(await view(w))).toBe('All types')
  await R.turnPage(w.gh, 1)
  await R.cycleType(w.gh)
  expect(last(w).query).toMatchObject({ type: 'page', page: '1' })
  expect(R.typeLabel(await view(w))).toBe('Pages')
  expect(await titles(w)).toEqual(['App 1'])
  await R.cycleType(w.gh)
  expect(R.typeLabel(await view(w))).toBe('Dashboards')
  expect(await titles(w)).toEqual(['App 2'])
  for (const label of ['Docs', 'Diagrams', 'Decks', 'Designs', 'All types']) {
    await R.cycleType(w.gh)
    expect(R.typeLabel(await view(w))).toBe(label)
  }
  expect(last(w).query.type).toBeUndefined()
  expect(await titles(w)).toEqual(['App 1', 'App 2', 'App 3'])
  expect(R.nextType('design')).toBe('')
  expect(R.nextType('')).toBe('page')
})

test('apps: paging over 24, Previous never below 1', async () => {
  const w = await signedInHost()
  w.s.apps = Array.from({ length: 30 }, (_, i) => app(i + 1))
  await A.openSection(w.gh, 'apps')
  expect(await titles(w)).toHaveLength(24)
  expect(R.pages(await view(w))).toBe(2)
  await R.turnPage(w.gh, 1)
  expect(await titles(w)).toHaveLength(6)
  expect(R.pageLine(await view(w), 6)).toBe('25–30 of 30')
  await R.turnPage(w.gh, -1)
  await R.turnPage(w.gh, -1)
  expect((await view(w)).page).toBe(1)
})

test('apps: Open goes to the browser pane on the desktop, a link in a terminal', async () => {
  const w = await signedInHost('desktop')
  await R.openApp(w.gh, app(1))
  expect(w.opened).toEqual(['https://rrotor.acme.test/apps/app-1/'])
  expect(await w.gh.state.note.get()).toEqual({ text: 'App 1 opened in the browser pane.', isError: false, link: 'https://rrotor.acme.test/apps/app-1/' })
  const t = await signedInHost('terminal')
  await R.openApp(t.gh, app(2))
  expect(t.opened).toEqual([])
  expect(await t.note()).toBe('App 2: open this link.')
  await R.openApp(t.gh, app(3, 'approved', { url: '' }))
  expect(await t.gh.state.note.get()).toEqual({ text: 'This app has no address yet.', isError: true })
})

test('apps: a reviewer sees the drafts, approves one, rejects one with a reason, retires one', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'apps')
  await R.viewApps(w.gh, 'draft')
  expect(await titles(w)).toEqual(['App 4'])
  await R.askReason(w.gh, 'a4')
  await R.rejectApp(w.gh, 'a4', '  ')
  expect(await w.gh.state.note.get()).toEqual({ text: 'Say why it is rejected: the person who published it reads the reason.', isError: true })
  expect(w.s.apps.find(a => a.id === 'a4')?.state).toBe('draft')
  await R.rejectApp(w.gh, 'a4', 'Numbers are wrong.')
  expect(last(w)).toMatchObject({ path: '/v1/apps', query: { state: 'draft' } })
  expect(w.s.calls.at(-2)).toMatchObject({ method: 'POST', path: '/v1/apps/a4/reject', body: { reason: 'Numbers are wrong.' } })
  expect(await w.note()).toBe('Rejected, with the reason.')
  expect((await view(w)).rejecting).toBeNull()
  expect(await titles(w)).toEqual([])
  await R.viewApps(w.gh, 'rejected')
  expect(await titles(w)).toEqual(['App 4', 'App 5'])
  await R.approveApp(w.gh, 'a5')
  expect(await w.note()).toBe('Approved: its people can open it now.')
  expect(w.s.apps.find(a => a.id === 'a5')?.state).toBe('approved')
  await R.viewApps(w.gh, 'approved')
  await R.retireApp(w.gh, 'a1')
  expect(await w.note()).toBe('Retired: no longer served or listed.')
  expect(await titles(w)).toEqual(['App 2', 'App 3', 'App 5'])
})

test("apps: a member is refused the drafts and the reviews, in the server's words", async () => {
  const w = await signedInHost()
  w.s.reviewer = false
  await A.openSection(w.gh, 'apps')
  expect(R.isReviewer(await w.gh.state.me.get())).toBe(false)
  await R.viewApps(w.gh, 'draft')
  expect(await w.gh.state.note.get()).toEqual({ text: 'Reviewers see the drafts. (trace tr-1)', isError: true })
  await R.approveApp(w.gh, 'a4')
  expect(await w.gh.state.note.get()).toEqual({ text: 'Only a reviewer may do that. (trace tr-1)', isError: true })
  expect(w.s.apps.find(a => a.id === 'a4')?.state).toBe('draft')
})

test('apps: the cards say the type, who published them, when, and for whom', () => {
  expect(R.typeChip(app(1))).toBe('Page')
  expect(R.typeChip(app(2))).toBe('Dashboard')
  expect(R.typeChip(app(6))).toBe('Design')
  expect(R.typeChip({})).toBe('Page')
  expect(R.publishedLine(app(1))).toBe('Published by Chris · 2026-11-01')
  expect(R.publishedLine({ submitted_by: null, submitted_at: null })).toBe('Published by someone')
  expect(R.rolesLine(app(1))).toBe('Everyone')
  expect(R.rolesLine(app(2))).toBe('sre')
})

test('publish: the command words, a path then --key value pairs, quotes kept', () => {
  expect(R.parsePublish('/tmp/x/board.html --name deploy-board --title "Deploy board" --type Dashboard --roles sre,Admin')).toEqual({
    path: '/tmp/x/board.html',
    name: 'deploy-board',
    title: 'Deploy board',
    type: 'dashboard',
    roles: ['sre', 'admin'],
  })
  expect(R.parsePublish("notes.md --description='A note' --title").description).toBe('A note')
  expect(R.parsePublish('')).toEqual({ roles: [] })
  expect(R.slug('Deploy Failures!.html')).toBe('deploy-failures')
  expect(R.slug('Release 1.6')).toBe('release-1-6')
  expect(R.slug('chart.png')).toBe('chart')
  expect(R.slug('---')).toBe('page')
})

test('publish: a page goes to the local rrotor as an app, and the reply says the type and who reviews it', async () => {
  const w = await signedInHost()
  w.files.set(`${HOME}/.glyphh/rrotor/token`, `${RROTOR_TOKEN}\n`)
  w.files.set('/tmp/board.html', '<!doctype html><title>Deploy board</title><p>hi</p>')
  const r = await glyphhCommand(w.gh, 'publish /tmp/board.html --description "Last week" --roles sre')
  expect(r.text).toBe('Published Deploy board (page) as deploy-board v1 to your rrotor. You review it: /glyphh apps. Open: http://127.0.0.1:7777/apps/deploy-board/')
  expect(w.s.published[0]).toMatchObject({ program: 'deploy-board', body: { name: 'deploy-board', title: 'Deploy board', description: 'Last week', type: 'page', roles: ['sre'], entry: 'index.html' } })
  expect((published(w, 0).files as Record<string, string>)['index.html']).toContain('<p>hi</p>')
  expect(w.s.calls.find(c => c.method === 'POST' && c.path === '/v1/apps')?.bearer).toBe(RROTOR_TOKEN)
  expect(await w.gh.state.note.get()).toMatchObject({ isError: false, link: 'http://127.0.0.1:7777/apps/deploy-board/' })

  w.s.reviewer = false
  w.files.set('/tmp/notes.md', '# Release notes\n\nAll good.')
  const md = await glyphhCommand(w.gh, 'publish /tmp/notes.md --name notes')
  expect(md.text).toStartWith("Published Release notes (doc) as notes v1 to your rrotor. Awaiting your organisation's admin or reviewer groups.")
  expect(w.s.published[1]).toMatchObject({ body: { entry: 'index.md', type: 'doc', description: 'Published from Claude Code: notes.md.' } })
})

test("publish: the type by the file's extension, or as --type says it; dashboard and deck are never inferred", async () => {
  const w = await signedInHost()
  w.files.set(`${HOME}/.glyphh/rrotor/token`, RROTOR_TOKEN)
  w.files.set('/tmp/board.html', '<title>Deploy failures</title>')
  w.files.set('/tmp/Chart.tsx', 'export default function Chart() { return <div /> }')
  w.files.set('/tmp/flow.mmd', 'sequenceDiagram\n  A->>B: hi')
  w.files.set('/tmp/logo.svg', '<svg xmlns="http://www.w3.org/2000/svg"/>')
  expect((await glyphhCommand(w.gh, 'publish /tmp/board.html --type dashboard')).text).toStartWith('Published Deploy failures (dashboard) as deploy-failures v1')
  expect(published(w, 0)).toMatchObject({ type: 'dashboard', entry: 'index.html' })
  expect((await glyphhCommand(w.gh, 'publish /tmp/Chart.tsx')).text).toStartWith('Published chart (page) as chart v1')
  expect(published(w, 1)).toMatchObject({ type: 'page', entry: 'index.tsx', files: { 'index.tsx': 'export default function Chart() { return <div /> }' } })
  expect((await glyphhCommand(w.gh, 'publish /tmp/flow.mmd --title "Sign-in flow"')).text).toStartWith('Published Sign-in flow (diagram) as sign-in-flow v1')
  expect(published(w, 2)).toMatchObject({ type: 'diagram', entry: 'index.mmd' })
  expect((await glyphhCommand(w.gh, 'publish /tmp/logo.svg')).text).toStartWith('Published logo (diagram) as logo v1')
  expect(published(w, 3)).toMatchObject({ type: 'diagram', entry: 'index.svg' })
})

test('publish: a PDF or an image goes as base64; a deck says so with --type', async () => {
  const w = await signedInHost()
  w.files.set(`${HOME}/.glyphh/rrotor/token`, RROTOR_TOKEN)
  w.files.set('/tmp/Q3 review.pdf', '%PDF-1.4 \u0000\u0001 binary')
  w.files.set('/tmp/home.png', '\u0089PNG\r\n')
  expect((await glyphhCommand(w.gh, 'publish "/tmp/Q3 review.pdf" --type deck --title "Q3 review"')).text).toStartWith('Published Q3 review (deck) as q3-review v1')
  expect(published(w, 0)).toMatchObject({ type: 'deck', entry: 'index.pdf', files: { 'index.pdf': { base64: btoa('%PDF-1.4 \u0000\u0001 binary') } } })
  expect((await glyphhCommand(w.gh, 'publish /tmp/home.png')).text).toStartWith('Published home (design) as home v1')
  expect(published(w, 1)).toMatchObject({ type: 'design', entry: 'index.png', files: { 'index.png': { base64: btoa('\u0089PNG\r\n') } } })
  w.files.set('/tmp/notes.pdf', '%PDF')
  expect((await glyphhCommand(w.gh, 'publish /tmp/notes.pdf')).text).toStartWith('Published notes (doc) as notes v1')
})

test('publish: no file, not an entry, a type outside the six, unreadable, no rrotor, rrotor down, and rrotor refusing, each said plainly', async () => {
  const w = await signedInHost()
  expect((await glyphhCommand(w.gh, 'publish')).text).toStartWith('Which file? Name what Claude wrote')
  expect((await glyphhCommand(w.gh, 'publish /tmp/x.py')).text).toStartWith(
    '/tmp/x.py: entry is a page (.html, .jsx, .tsx), a document (.md, .pdf), a diagram (.mmd, .svg) or an image.',
  )
  expect((await glyphhCommand(w.gh, 'publish /tmp/board.html --type slides')).text).toStartWith('slides is not a type: page, dashboard, doc, diagram, deck or design.')
  expect(w.s.calls.some(c => c.path === '/v1/apps')).toBe(false)
  expect((await glyphhCommand(w.gh, 'publish /tmp/missing.html')).text).toBe('Cannot read /tmp/missing.html.')
  expect((await glyphhCommand(w.gh, 'publish /tmp/missing.pdf')).text).toBe('Cannot read /tmp/missing.pdf.')
  w.files.set('/tmp/board.html', '<p>hi</p>')
  expect((await glyphhCommand(w.gh, 'publish /tmp/board.html')).text).toStartWith('No rrotor on this machine')
  w.files.set(`${HOME}/.glyphh/rrotor/token`, RROTOR_TOKEN)
  w.s.rrotorDown = true
  expect((await glyphhCommand(w.gh, 'publish /tmp/board.html')).text).toBe('rrotor is not answering at http://127.0.0.1:7777: start it ("start rrotor", the rrotor skill).')
  w.s.rrotorDown = false
  const refused = await glyphhCommand(w.gh, 'publish /tmp/board.html --name "Not A Name"')
  expect(refused.text).toBe('Not A Name is not a program name: ^[a-z][a-z0-9-]{0,62}$.')
  expect(await w.gh.state.note.get()).toMatchObject({ isError: true })
  w.files.set(`${HOME}/.glyphh/rrotor/token`, 'wrong')
  expect((await glyphhCommand(w.gh, 'publish /tmp/board.html')).text).toBe('Send the local token: Authorization: Bearer <local token>.')
})

test('publish: signed out, the command asks for the sign-in first', async () => {
  const w = fakeHost()
  expect((await glyphhCommand(w.gh, 'publish /tmp/board.html')).text).toStartWith('Sign in to Glyphh first: /glyphh signin')
})

test('/glyphh artifacts is not a command: the usage line names apps', async () => {
  const w = await signedInHost()
  expect((await glyphhCommand(w.gh, 'artifacts')).text).toBe('Usage: /glyphh [login | logout | account | org | plan | billing | apps | publish <file> | link]')
})
