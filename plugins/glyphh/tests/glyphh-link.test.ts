// Linking this machine's rrotor to Glyphh: the server issues the runtime
// token to the install, rrotor takes it and connects; /glyphh link and the
// Account section's Link say where it stands.
import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import * as A from '../hooks/glyphh/actions'
import { glyphhCommand } from '../hooks/glyphh/command'
import * as L from '../hooks/glyphh/link'
import { HOME, fakeHost, settle } from './fake-host'
import { RROTOR_TOKEN } from './fake-server'

async function signedInHost() {
  const w = fakeHost()
  await signedIn(w.gh, 'i1', w.server.TOKEN)
  return w
}

const withRrotor = (w: ReturnType<typeof fakeHost>) => w.files.set(`${HOME}/.glyphh/rrotor/token`, `${RROTOR_TOKEN}\n`)

const LINKED = "Linked to Glyphh as rt-local-1: it shows on the platform's Runtimes page, and its apps reach your organisation's catalogue."

test('link: where the rrotor stands, as one line', async () => {
  const w = await signedInHost()
  expect(await L.rrotorHealth(w.gh)).toEqual({ status: 'none' })
  expect(L.linkLine({ status: 'none' })).toBe('No rrotor on this machine: ask Claude to "install rrotor".')
  withRrotor(w)
  w.s.rrotorDown = true
  expect(await L.rrotorHealth(w.gh)).toEqual({ status: 'down' })
  expect(L.linkLine({ status: 'down' })).toBe('rrotor not running: ask Claude to "start rrotor".')
  w.s.rrotorDown = false
  const up = await L.rrotorHealth(w.gh)
  expect(up).toEqual({ status: 'up', version: '0.2.0', runtime_id: null, link: 'no_token' })
  expect(L.linkLine(up)).toBe('Not linked (rrotor 0.2.0)')
  expect(L.isLinked(up)).toBe(false)
  expect(L.linkLine({ status: 'up', version: '0.2.0', runtime_id: 'rt-local-1', link: 'online' })).toBe('Linked as rt-local-1 (rrotor 0.2.0)')
  expect(L.linkLine({ status: 'up', version: '0.2.0', runtime_id: 'rt-local-1', link: 'backoff' })).toBe('Linking… (backoff, rrotor 0.2.0)')
  expect(L.linkLine({ status: 'up', version: '0.2.0', runtime_id: null, link: 'off' })).toBe('Link off (rrotor 0.2.0)')
  expect(L.linkLine({ status: 'up', version: '0.2.0', runtime_id: 'rt-local-1', link: 'upgrade_needed' })).toBe('Link upgrade needed (rrotor 0.2.0)')
  w.files.set(`${HOME}/.glyphh/rrotor/token`, 'wrong')
  await expect(L.rrotorHealth(w.gh)).rejects.toThrow('Send the local token: Authorization: Bearer <local token>.')
})

test('link: the server issues the token to the install, rrotor takes it, and linking again rotates it', async () => {
  const w = await signedInHost()
  withRrotor(w)
  expect((await glyphhCommand(w.gh, 'link')).text).toBe(LINKED)
  const issued = w.s.calls.find(c => c.path === '/v1/runtime/local')!
  expect(issued).toMatchObject({ method: 'POST', bearer: w.server.TOKEN })
  const handed = w.s.calls.find(c => c.path === '/v1/runtime/token')!
  expect(handed).toMatchObject({ method: 'PUT', bearer: RROTOR_TOKEN, body: { runtime_id: 'rt-local-1', token: 'rtok-1' } })
  expect(w.s.calls.indexOf(issued)).toBeLessThan(w.s.calls.indexOf(handed))
  expect(w.s.rrotor).toMatchObject({ runtime_id: 'rt-local-1', link: 'online' })
  expect(await L.rrotorHealth(w.gh)).toMatchObject({ link: 'online', runtime_id: 'rt-local-1' })

  expect((await glyphhCommand(w.gh, 'link')).text).toBe(LINKED)
  expect(w.s.tokens.map(t => t.token)).toEqual(['rtok-1', 'rtok-2'])
})

test('link: the Account section shows the state and its Link button acts, then shows it again', async () => {
  const w = await signedInHost()
  withRrotor(w)
  await A.openSection(w.gh, 'account')
  expect((await w.gh.state.lists.get()).rrotor).toEqual([{ status: 'up', version: '0.2.0', runtime_id: null, link: 'no_token' }])
  await A.linkLocalRrotor(w.gh)
  expect(await w.note()).toBe(LINKED)
  expect((await w.gh.state.lists.get()).rrotor).toEqual([{ status: 'up', version: '0.2.0', runtime_id: 'rt-local-1', link: 'online' }])
  w.s.noInstall = true
  await A.linkLocalRrotor(w.gh)
  expect(await w.gh.state.note.get()).toEqual({ text: 'A local runtime belongs to an install: link it from Claude Code. (trace tr-1)', isError: true })
  expect((await w.gh.state.lists.get()).rrotor?.[0]).toMatchObject({ link: 'online' })
  w.files.delete(`${HOME}/.glyphh/rrotor/token`)
  await A.openSection(w.gh, 'account')
  expect((await w.gh.state.lists.get()).rrotor).toEqual([{ status: 'none' }])
})

test('link: a link still connecting after twenty seconds is said so, and the platform shows it once online', async () => {
  const w = await signedInHost()
  withRrotor(w)
  w.s.linkStalls = true
  const linking = glyphhCommand(w.gh, 'link')
  await settle()
  await w.advance(21_000)
  expect((await linking).text).toBe('rrotor took the token (rt-local-1) and is still connecting; the platform shows it once it is online.')
  w.s.linkStalls = false
  w.s.linkOutcome = 'refused'
  expect((await glyphhCommand(w.gh, 'link')).text).toBe("rrotor took the token but the link refused: check the container's log.")
})

test("link: signed out, no rrotor, rrotor down, and the server's refusal, each said plainly", async () => {
  const out = fakeHost()
  expect((await glyphhCommand(out.gh, 'link')).text).toStartWith('Sign in to Glyphh first: /glyphh signin')
  const w = await signedInHost()
  expect((await glyphhCommand(w.gh, 'link')).text).toBe('No rrotor on this machine: ask Claude to "install rrotor" first (the rrotor skill).')
  withRrotor(w)
  w.s.rrotorDown = true
  expect((await glyphhCommand(w.gh, 'link')).text).toBe('rrotor is not answering at http://127.0.0.1:7777: start it ("start rrotor", the rrotor skill).')
  w.s.rrotorDown = false
  w.s.noInstall = true
  expect((await glyphhCommand(w.gh, 'link')).text).toBe('A local runtime belongs to an install: link it from Claude Code. (trace tr-1)')
  expect(w.s.tokens).toEqual([])
  w.s.noInstall = false
  w.files.set(`${HOME}/.glyphh/rrotor/token`, 'wrong')
  expect((await glyphhCommand(w.gh, 'link')).text).toBe('Send the local token: Authorization: Bearer <local token>.')
})
