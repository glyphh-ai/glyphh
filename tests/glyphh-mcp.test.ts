// The sign-in card's server logic (mcp/src/flow.ts) on the fake server: no
// network, a clock that moves when told, install.json kept in memory.
import { expect, test } from 'claude-code/testing'

import { SignIn, cardText, type Deps, type Install } from '../mcp/src/flow'
import { fakeServer } from './fake-server'

const MACHINE = 'a'.repeat(64)

function world(opts: { install?: Install; down?: boolean } = {}) {
  const server = fakeServer()
  const kept: Install[] = []
  let now = Date.parse('2026-10-14T12:00:00Z')
  let install = opts.install
  const deps: Deps = {
    server: 'https://glyphh.test',
    http: async (method, url, body, bearer) => {
      if (opts.down) throw new Error('fetch failed')
      const headers: Record<string, string> = bearer ? { Authorization: `Bearer ${bearer}` } : {}
      const r = await server.fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
      return { status: r.status, text: r.text }
    },
    now: () => now,
    install: async () => install,
    keep: async i => void (kept.push(i), (install = i)),
    device: { name: 'testmac', surface: 'desktop', mod_version: '0.1.0' },
    machineId: async () => MACHINE,
  }
  const polls = () => server.s.calls.filter(c => c.path === '/v1/device/token').length
  return { flow: new SignIn(deps), s: server.s, kept, polls, advance: (ms: number) => void (now += ms), TOKEN: server.TOKEN }
}

test('mcp sign-in: the card, polls no faster than the server allows, install.json kept', async () => {
  const w = world()
  const card = await w.flow.start()
  expect(card).toMatchObject({ state: 'pending', user_code: 'ABCD-EFGH', verification_uri_complete: 'https://glyphh.test/v1/device?code=ABCD-EFGH' })
  expect(w.s.calls[0]).toMatchObject({ path: '/v1/device/code', body: { name: 'testmac', surface: 'desktop', machine_id: MACHINE } })
  expect(w.s.calls[0]?.bearer).toBeUndefined()

  expect(await w.flow.status()).toEqual({ status: 'pending' })
  expect(w.polls()).toBe(0) // before the interval: the server is not asked
  w.advance(5_000)
  expect(await w.flow.status()).toEqual({ status: 'pending' }) // authorization_pending
  w.advance(5_000)
  expect(await w.flow.status()).toEqual({ status: 'pending' }) // slow_down: 10 s now
  w.advance(5_000)
  await w.flow.status()
  expect(w.polls()).toBe(2)
  w.advance(5_000)
  expect(await w.flow.status()).toEqual({ status: 'signed_in', email: 'chris@example.com' })
  expect(w.kept).toEqual([{ install_id: 'i1', token: w.TOKEN }])
  const calls = w.s.calls.length
  expect(await w.flow.status()).toEqual({ status: 'signed_in', email: 'chris@example.com' })
  expect(w.s.calls.length).toBe(calls)
})

test('mcp sign-in: already signed in says who; a revoked install signs in again', async () => {
  const w = world({ install: { install_id: 'i1', token: 'tok-secret-1' } })
  expect(await w.flow.start()).toEqual({ state: 'signed_in', email: 'chris@example.com' })
  expect(w.s.calls.map(c => c.path)).toEqual(['/v1/me'])
  expect(cardText({ state: 'signed_in', email: 'chris@example.com' })).toBe('Signed in as chris@example.com.')

  const revoked = world({ install: { install_id: 'i1', token: 'old' } })
  expect(await revoked.flow.start()).toMatchObject({ state: 'pending' })
})

test('mcp sign-in: asking again while a code waits keeps that code, and finishes it once approved', async () => {
  const w = world()
  w.s.polls = ['authorization_pending', 'ok']
  await w.flow.start()
  w.advance(5_000)
  expect(await w.flow.start()).toMatchObject({ state: 'pending', user_code: 'ABCD-EFGH' })
  expect(w.s.calls.filter(c => c.path === '/v1/device/code').length).toBe(1)
  w.advance(5_000)
  expect(await w.flow.start()).toEqual({ state: 'signed_in', email: 'chris@example.com' })
  expect(cardText({ state: 'pending', user_code: 'X', verification_uri: 'u', verification_uri_complete: 'u?c', expires_at: 0 })).toContain('u?c')
})

test('mcp sign-in: expired, declined, out of time, refused and unreachable', async () => {
  for (const [answer, status] of [['expired_token', 'expired'], ['access_denied', 'denied'], ['E_BOOM', 'error']] as const) {
    const w = world()
    w.s.polls = [answer]
    await w.flow.start()
    w.advance(5_000)
    expect((await w.flow.status()).status).toBe(status)
    expect(w.flow.pending).toBeUndefined()
    expect(w.kept).toEqual([])
  }
  const late = world()
  late.s.polls = Array(200).fill('authorization_pending')
  await late.flow.start()
  late.advance(600_000)
  expect(await late.flow.status()).toEqual({ status: 'expired' })
  expect(await world().flow.status()).toEqual({ status: 'expired' }) // nothing pending

  await expect(world({ down: true }).flow.start()).rejects.toThrow('Cannot reach the Glyphh server at https://glyphh.test.')
})
