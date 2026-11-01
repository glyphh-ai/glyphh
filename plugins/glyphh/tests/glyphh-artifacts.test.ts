// The Artifacts section's actions against the fake catalogue, and /glyphh
// publish against the fake local rrotor.
import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import * as A from '../hooks/glyphh/actions'
import * as R from '../hooks/glyphh/artifacts'
import { glyphhCommand } from '../hooks/glyphh/command'
import { HOME, fakeHost } from './fake-host'
import { RROTOR_TOKEN, artifact } from './fake-server'

async function signedInHost(surface: 'desktop' | 'terminal' = 'desktop') {
  const w = fakeHost({ surface })
  await signedIn(w.gh, 'i1', w.server.TOKEN)
  return w
}

const titles = async (w: ReturnType<typeof fakeHost>) => ((await w.gh.state.lists.get()).artifacts ?? []).map(a => a.title)
const last = (w: ReturnType<typeof fakeHost>) => w.s.calls.at(-1)!

test('artifacts: opening the section lists the published page, 24 a page, by the state asked', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'artifacts')
  expect(await titles(w)).toEqual(['Page 1', 'Page 2', 'Page 3'])
  expect(last(w)).toMatchObject({ path: '/v1/artifacts', query: { page: '1', per_page: '24', state: 'approved' } })
  expect(await w.gh.state.artifacts.get()).toMatchObject({ total: 3, page: 1, state: 'approved' })
  expect(R.pageLine(await w.gh.state.artifacts.get(), 3)).toBe('1–3 of 3')
})

test('artifacts: search narrows by title, description or name and goes back to page 1', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'artifacts')
  await R.turnPage(w.gh, 1)
  await R.searchArtifacts(w.gh, ' page-2 ')
  expect(last(w).query).toMatchObject({ q: 'page-2', page: '1' })
  expect(await titles(w)).toEqual(['Page 2'])
  await R.searchArtifacts(w.gh, 'nothing-like-it')
  expect(await titles(w)).toEqual([])
  expect(R.pageLine(await w.gh.state.artifacts.get(), 0)).toBe('Nothing here.')
})

test('artifacts: paging over 24, Previous never below 1', async () => {
  const w = await signedInHost()
  w.s.artifacts = Array.from({ length: 30 }, (_, i) => artifact(i + 1))
  await A.openSection(w.gh, 'artifacts')
  expect(await titles(w)).toHaveLength(24)
  expect(R.pages(await w.gh.state.artifacts.get())).toBe(2)
  await R.turnPage(w.gh, 1)
  expect(await titles(w)).toHaveLength(6)
  expect(R.pageLine(await w.gh.state.artifacts.get(), 6)).toBe('25–30 of 30')
  await R.turnPage(w.gh, -1)
  await R.turnPage(w.gh, -1)
  expect((await w.gh.state.artifacts.get()).page).toBe(1)
})

test('artifacts: Open goes to the browser pane on the desktop, a link in a terminal', async () => {
  const w = await signedInHost('desktop')
  await R.openArtifact(w.gh, artifact(1))
  expect(w.opened).toEqual(['https://rrotor.acme.test/apps/page-1/'])
  expect(await w.gh.state.note.get()).toEqual({ text: 'Page 1 opened in the browser pane.', isError: false, link: 'https://rrotor.acme.test/apps/page-1/' })
  const t = await signedInHost('terminal')
  await R.openArtifact(t.gh, artifact(2))
  expect(t.opened).toEqual([])
  expect(await t.note()).toBe('Page 2: open this link.')
  await R.openArtifact(t.gh, artifact(3, 'approved', { url: '' }))
  expect(await t.gh.state.note.get()).toEqual({ text: 'This artifact has no address yet.', isError: true })
})

test('artifacts: a reviewer sees the drafts, approves one, rejects one with a reason, retires one', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'artifacts')
  await R.viewArtifacts(w.gh, 'draft')
  expect(await titles(w)).toEqual(['Page 4'])
  await R.askReason(w.gh, 'a4')
  await R.rejectArtifact(w.gh, 'a4', '  ')
  expect(await w.gh.state.note.get()).toEqual({ text: 'Say why it is rejected: the person who published it reads the reason.', isError: true })
  expect(w.s.artifacts.find(a => a.id === 'a4')?.state).toBe('draft')
  await R.rejectArtifact(w.gh, 'a4', 'Numbers are wrong.')
  expect(last(w)).toMatchObject({ path: '/v1/artifacts', query: { state: 'draft' } })
  expect(w.s.calls.at(-2)).toMatchObject({ method: 'POST', path: '/v1/artifacts/a4/reject', body: { reason: 'Numbers are wrong.' } })
  expect(await w.note()).toBe('Rejected, with the reason.')
  expect((await w.gh.state.artifacts.get()).rejecting).toBeNull()
  expect(await titles(w)).toEqual([])
  await R.viewArtifacts(w.gh, 'rejected')
  expect(await titles(w)).toEqual(['Page 4', 'Page 5'])
  await R.approveArtifact(w.gh, 'a5')
  expect(await w.note()).toBe('Approved: its people can open it now.')
  expect(w.s.artifacts.find(a => a.id === 'a5')?.state).toBe('approved')
  await R.viewArtifacts(w.gh, 'approved')
  await R.retireArtifact(w.gh, 'a1')
  expect(await w.note()).toBe('Retired: no longer served or listed.')
  expect(await titles(w)).toEqual(['Page 2', 'Page 3', 'Page 5'])
})

test("artifacts: a member is refused the drafts and the reviews, in the server's words", async () => {
  const w = await signedInHost()
  w.s.reviewer = false
  await A.openSection(w.gh, 'artifacts')
  expect(R.isReviewer(await w.gh.state.me.get())).toBe(false)
  await R.viewArtifacts(w.gh, 'draft')
  expect(await w.gh.state.note.get()).toEqual({ text: 'Reviewers see the drafts. (trace tr-1)', isError: true })
  await R.approveArtifact(w.gh, 'a4')
  expect(await w.gh.state.note.get()).toEqual({ text: 'Only a reviewer may do that. (trace tr-1)', isError: true })
  expect(w.s.artifacts.find(a => a.id === 'a4')?.state).toBe('draft')
})

test('artifacts: the cards say who published them, when, and for whom', () => {
  expect(R.publishedLine(artifact(1))).toBe('Published by Chris · 2026-11-01')
  expect(R.publishedLine({ submitted_by: null, submitted_at: null })).toBe('Published by someone')
  expect(R.rolesLine(artifact(1))).toBe('Everyone')
  expect(R.rolesLine(artifact(2))).toBe('sre')
})

test('publish: the command words, a path then --key value pairs, quotes kept', () => {
  expect(R.parsePublish('/tmp/x/board.html --name deploy-board --title "Deploy board" --roles sre,Admin')).toEqual({
    path: '/tmp/x/board.html',
    name: 'deploy-board',
    title: 'Deploy board',
    roles: ['sre', 'admin'],
  })
  expect(R.parsePublish("notes.md --description='A note' --title").description).toBe('A note')
  expect(R.parsePublish('')).toEqual({ roles: [] })
  expect(R.slug('Deploy Failures!.html')).toBe('deploy-failures')
  expect(R.slug('---')).toBe('page')
})

test('publish: a page goes to the local rrotor as an app, and the reply says who reviews it', async () => {
  const w = await signedInHost()
  w.files.set(`${HOME}/.glyphh/rrotor/token`, `${RROTOR_TOKEN}\n`)
  w.files.set('/tmp/board.html', '<!doctype html><title>Deploy board</title><p>hi</p>')
  const r = await glyphhCommand(w.gh, 'publish /tmp/board.html --description "Last week" --roles sre')
  expect(r.text).toBe('Published Deploy board as deploy-board v1 to your rrotor. You review it: /glyphh artifacts. Open: http://127.0.0.1:7777/apps/deploy-board/')
  expect(w.s.apps[0]).toMatchObject({ program: 'deploy-board', body: { name: 'deploy-board', title: 'Deploy board', description: 'Last week', roles: ['sre'], entry: 'index.html' } })
  expect((w.s.apps[0]!.body as { files: Record<string, string> }).files['index.html']).toContain('<p>hi</p>')
  expect(w.s.calls.find(c => c.path === '/v1/apps')?.bearer).toBe(RROTOR_TOKEN)
  expect(await w.gh.state.note.get()).toMatchObject({ isError: false, link: 'http://127.0.0.1:7777/apps/deploy-board/' })

  w.s.reviewer = false
  w.files.set('/tmp/notes.md', '# Release notes\n\nAll good.')
  const md = await glyphhCommand(w.gh, 'publish /tmp/notes.md --name notes')
  expect(md.text).toStartWith("Published Release notes as notes v1 to your rrotor. Awaiting your organisation's admin or reviewer groups.")
  expect(w.s.apps[1]).toMatchObject({ body: { entry: 'index.md', description: 'Published from Claude Code: notes.md.' } })
})

test('publish: no file, not a page, unreadable, no rrotor, rrotor down, and rrotor refusing, each said plainly', async () => {
  const w = await signedInHost()
  expect((await glyphhCommand(w.gh, 'publish')).text).toStartWith('Which file? Name the page Claude wrote')
  expect((await glyphhCommand(w.gh, 'publish /tmp/x.py')).text).toStartWith('/tmp/x.py is not a page')
  expect((await glyphhCommand(w.gh, 'publish /tmp/missing.html')).text).toBe('Cannot read /tmp/missing.html.')
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
