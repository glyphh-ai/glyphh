import { expect, test } from 'claude-code/testing'

import { signOut, signedIn } from '../hooks/glyphh/account'
import { ApiError, api, describe } from '../hooks/glyphh/api'
import { HOME, fakeHost } from './fake-host'

const signIn = async (w: ReturnType<typeof fakeHost>) => signedIn(w.gh, 'i1', w.server.TOKEN)

test('client: api.glyphh.ai by default, GLYPHH_SERVER_URL when set, the install token as bearer', async () => {
  const w = fakeHost()
  await expect(api(w.gh, 'GET', '/v1/me')).rejects.toThrow('Not signed in.')
  expect(w.s.calls).toHaveLength(0) // no token, no call
  await signIn(w)
  const urls: string[] = []
  const fetch = w.gh.http.fetch
  w.gh.http.fetch = (url, init) => (urls.push(url), fetch(url, init))
  await api(w.gh, 'GET', '/v1/me')
  expect(urls.at(-1)).toBe('https://api.glyphh.ai/v1/me')
  expect(w.s.calls.at(-1)?.bearer).toBe(w.server.TOKEN)

  const other = fakeHost({ server: 'https://api.glyphh.test/' })
  const seen: string[] = []
  other.gh.http.fetch = async url => (seen.push(url), { status: 200, ok: true, headers: {}, text: '[]' })
  await api(other.gh, 'GET', '/v1/plans', undefined, { auth: false })
  expect(seen).toEqual(['https://api.glyphh.test/v1/plans'])
})

test('client: refusals read as {error: {code, message, trace_id}}; E_LIMIT names limit, use and plan', async () => {
  const w = fakeHost()
  await signIn(w)
  const err = await api(w.gh, 'POST', '/v1/billing/checkout', { plan: 'Enterprise' }).catch(e => e)
  expect(err).toBeInstanceOf(ApiError)
  expect(err).toMatchObject({ code: 'E_INVALID', status: 422, detail: { reason: 'not_self_serve' } })
  expect(describe(err)).toBe('Enterprise is by contract: talk to us at sales@glyphh.ai. (trace tr-1)')
  // The month's reads used up on Free, as glyphh_ada.api.meter says it.
  const said = "Your Free plan's 5,000 Ada reads this month are used: they start again on 2026-11-01. Upgrade to Basic (the connector's upgrade tool, or Billing on the platform) to read on now."
  const limit = new ApiError('E_LIMIT', said, 429, { reason: 'requests', used: 5000, max: 5000, plan: 'Free', upgrade: 'Basic', resets_at: '2026-11-01' }, 'tr-2')
  expect(describe(limit)).toBe(`${said} (5,000 of 5,000 reads used) (trace tr-2)`)
  const missing = await api(w.gh, 'DELETE', '/v1/nothing/zzz').catch(e => e)
  expect(describe(missing)).toBe('No route DELETE /v1/nothing/zzz (trace tr-1)')
})

test('client: an unreachable server says where it looked', async () => {
  const w = fakeHost()
  w.gh.http.fetch = async () => {
    throw new Error('ECONNREFUSED')
  }
  const err = await api(w.gh, 'GET', '/v1/plans', undefined, { auth: false }).catch(e => e)
  expect(describe(err)).toBe('Cannot reach the Glyphh server at https://api.glyphh.ai.')
})

test('storage: install.json is written 0600 through the umask writer, never fs.write', async () => {
  const w = fakeHost()
  const writes: string[] = []
  const write = w.gh.fs.write
  w.gh.fs.write = (p, t) => (writes.push(p), write(p, t))
  await signIn(w)
  const path = `${HOME}/.glyphh/install.json`
  expect(JSON.parse(w.files.get(path)!)).toEqual({ install_id: 'i1', token: w.server.TOKEN })
  expect(w.modes.get(path)).toBe('600')
  expect(writes).not.toContain(path)
  expect(w.argvs.find(a => a[0] === '/bin/sh')?.join(' ')).not.toContain(w.server.TOKEN) // stdin only
  expect(await w.note()).toBe('Signed in.')
  expect(w.s.calls.some(c => c.path.startsWith('/v1/license'))).toBe(false) // no licence: Ada Cloud is the product
})

test('sign-out forgets install.json and a licence.json an older plugin left', async () => {
  const w = fakeHost()
  await signIn(w)
  w.files.set(`${HOME}/.glyphh/license.json`, '{}')
  await signOut(w.gh)
  expect(w.files.has(`${HOME}/.glyphh/install.json`)).toBe(false)
  expect(w.files.has(`${HOME}/.glyphh/license.json`)).toBe(false)
})
