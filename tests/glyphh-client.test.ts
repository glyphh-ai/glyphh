import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import { ApiError, api, describe } from '../hooks/glyphh/api'
import { keyPair } from '../hooks/glyphh/ed25519'
import { allows, canonical, check, loadLicense, refreshLicense } from '../hooks/glyphh/license'
import { HOME, fakeHost } from './fake-host'

const signIn = async (w: ReturnType<typeof fakeHost>) => signedIn(w.gh, 'i1', w.server.TOKEN)

test('client: localhost:8080 by default, GLYPHH_SERVER_URL when set, the install token as bearer', async () => {
  const w = fakeHost()
  await expect(api(w.gh, 'GET', '/v1/me')).rejects.toThrow('Not signed in.')
  expect(w.s.calls).toHaveLength(0) // no token, no call
  await signIn(w)
  const urls: string[] = []
  const fetch = w.gh.http.fetch
  w.gh.http.fetch = (url, init) => (urls.push(url), fetch(url, init))
  await api(w.gh, 'GET', '/v1/me')
  expect(urls.at(-1)).toBe('http://localhost:8080/v1/me')
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
  w.s.maxMembers = 2
  const err = await api(w.gh, 'POST', '/v1/org/invites', { email: 'c@example.com' }).catch(e => e)
  expect(err).toBeInstanceOf(ApiError)
  expect((err as ApiError).code).toBe('E_LIMIT')
  expect(describe(err)).toBe('Upgrade to add more. (2 of 2 members used) (trace tr-1)')
  const missing = await api(w.gh, 'DELETE', '/v1/nothing/zzz').catch(e => e)
  expect(describe(missing)).toBe('No route DELETE /v1/nothing/zzz (trace tr-1)')
})

test('client: an unreachable server says where it looked', async () => {
  const w = fakeHost()
  w.gh.http.fetch = async () => {
    throw new Error('ECONNREFUSED')
  }
  const err = await api(w.gh, 'GET', '/v1/plans', undefined, { auth: false }).catch(e => e)
  expect(describe(err)).toBe('Cannot reach the Glyphh server at http://localhost:8080.')
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
})

test('license: checked with Ed25519 against the key, kept, and gates RPA', async () => {
  const w = fakeHost()
  await signIn(w) // fetches the license too
  const info = await w.gh.state.license.get()
  expect(info?.ok).toBe(true)
  expect(info?.plan).toBe('Pro')
  expect(allows(info, 'rpa')).toBe(true)
  expect(w.files.has(`${HOME}/.glyphh/license.json`)).toBe(true)
  expect((await loadLicense(w.gh))?.ok).toBe(true)

  w.s.licenseTamper = true
  w.files.delete(`${HOME}/.glyphh/license.json`)
  const bad = await refreshLicense(w.gh)
  expect(bad.ok).toBe(false)
  expect(bad.error).toBe('signature does not check out')
  expect(allows(bad, 'rpa')).toBe(false)
  expect(w.files.has(`${HOME}/.glyphh/license.json`)).toBe(false) // a bad one is never kept
})

test('license: expired is not valid; JWS and canonical-JSON forms check too', async () => {
  const w = fakeHost()
  w.s.licenseExpires = '2000-01-01T00:00:00Z'
  await signIn(w)
  expect(await w.gh.state.license.get()).toMatchObject({ ok: false, error: 'expired' })

  const { publicKey, sign } = await keyPair(new Uint8Array(32).fill(3))
  const b64 = (b: Uint8Array) => btoa(String.fromCharCode(...b))
  const b64u = (b: Uint8Array) => b64(b).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const key = { kty: 'OKP', crv: 'Ed25519', x: b64u(publicKey) }
  const claims = { plan: 'Team', features: { rpa: true }, limits: { max_members: null } }
  const head = b64u(new TextEncoder().encode('{"alg":"EdDSA"}'))
  const body = b64u(new TextEncoder().encode(JSON.stringify(claims)))
  const jws = `${head}.${body}.${b64u(await sign(new TextEncoder().encode(`${head}.${body}`)))}`
  expect((await check({ token: jws }, key, 0)).ok).toBe(true)
  const sig = b64(await sign(new TextEncoder().encode(canonical(claims))))
  expect(await check({ license: claims, signature: sig }, { public_key: b64(publicKey) }, 0)).toMatchObject({ ok: true, plan: 'Team' })
  expect(canonical({ b: 1, a: 'é' })).toBe('{"a":"\\u00e9","b":1}')
})

test("license: the server's own answer, signed by glyphh_server.ops.license, checks", async () => {
  const payload = {
    install_id: '11111111-1111-1111-1111-111111111111',
    user_id: '22222222-2222-2222-2222-222222222222',
    org_id: '33333333-3333-3333-3333-333333333333',
    plan: 'Café Pro',
    limits: { max_members: 1, max_installs: 5 },
    features: { rpa: true },
    expires_at: '2099-01-01T00:00:00Z',
  }
  const signature = '8wRzw8Grb8P5e8I7J/wzxWkE1DhN+jB/uizcHLN/b6mvP6WCcti2Q9e19+uhyoLdJ6N6Oa+fw5ZSW5NZK4IPDw=='
  const key = { alg: 'Ed25519', public_key: 'NdI9aO1bIfswQd7y1XukRN8DwQCqqRAh84wB4libVgE=' }
  expect(await check({ payload, signature }, key, 0)).toMatchObject({ ok: true, plan: 'Café Pro', features: { rpa: true } })
  expect((await check({ payload: { ...payload, plan: 'Team' }, signature }, key, 0)).ok).toBe(false)
})
