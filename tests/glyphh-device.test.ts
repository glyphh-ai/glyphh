import { expect, test } from 'claude-code/testing'

import { startSignIn, stopPolling } from '../hooks/glyphh/device'
import { HOME, fakeHost, settle } from './fake-host'

const tokenPolls = (w: ReturnType<typeof fakeHost>) => w.s.calls.filter(c => c.path === '/v1/device/token').length

test('device flow: code shown, link opened in the browser pane, polls honour interval and slow_down', async () => {
  const w = fakeHost({ surface: 'desktop' })
  const started = await startSignIn(w.gh)
  expect(started).toMatchObject({ status: 'pending', user_code: 'ABCD-EFGH', interval: 5, opened: true })
  expect(w.opened).toEqual(['https://glyphh.test/v1/device?code=ABCD-EFGH'])
  expect(w.s.calls[0]).toMatchObject({ path: '/v1/device/code', body: { name: 'testmac', surface: 'desktop' } })
  expect(w.s.calls[0]?.bearer).toBeUndefined()

  await w.advance(4_000)
  expect(tokenPolls(w)).toBe(0) // not before the interval
  await w.advance(1_000)
  expect(tokenPolls(w)).toBe(1) // authorization_pending
  await w.advance(5_000)
  expect(tokenPolls(w)).toBe(2) // slow_down: the interval grows by 5 s
  expect(await w.gh.state.auth.get()).toMatchObject({ status: 'pending', interval: 10 })
  await w.advance(5_000)
  expect(tokenPolls(w)).toBe(2)
  await w.advance(5_000)
  expect(tokenPolls(w)).toBe(3) // the token
  expect(await w.gh.state.auth.get()).toEqual({ status: 'in', install_id: 'i1' })
  expect(w.modes.get(`${HOME}/.glyphh/install.json`)).toBe('600')
  expect((await w.gh.state.me.get())?.user).toMatchObject({ email: 'chris@example.com' })

  await w.advance(60_000)
  expect(tokenPolls(w)).toBe(3) // polling stopped
})

test('device flow: in a terminal the link is printed, not opened', async () => {
  const w = fakeHost({ surface: 'terminal' })
  const started = await startSignIn(w.gh)
  expect(started).toMatchObject({ opened: false, verification_uri_complete: 'https://glyphh.test/v1/device?code=ABCD-EFGH' })
  expect(w.opened).toEqual([])
  expect(w.s.calls[0]?.body).toMatchObject({ surface: 'cli' })
  stopPolling()
})

test('device flow: expired, declined and refused codes end the sign-in with a reason', async () => {
  for (const [answer, said] of [
    ['expired_token', 'The code expired. Sign in again.'],
    ['access_denied', 'Sign-in was declined.'],
  ] as const) {
    const w = fakeHost()
    w.s.polls = [answer]
    await startSignIn(w.gh)
    await w.advance(5_000)
    expect(await w.gh.state.auth.get()).toEqual({ status: 'out', error: said })
    expect(w.files.has(`${HOME}/.glyphh/install.json`)).toBe(false)
  }
  const late = fakeHost()
  late.s.polls = Array(200).fill('authorization_pending')
  await startSignIn(late.gh)
  for (let i = 0; i < 125; i++) await late.advance(5_000)
  expect(await late.gh.state.auth.get()).toEqual({ status: 'out', error: 'The code expired. Sign in again.' })
})

test('device flow: an install past the plan limit is refused with the limit', async () => {
  const w = fakeHost()
  const fetch = w.gh.http.fetch
  w.gh.http.fetch = async (url, init) =>
    url.endsWith('/v1/device/token')
      ? { status: 403, ok: false, headers: {}, text: JSON.stringify({ error: { code: 'E_LIMIT', message: '', trace_id: 't', limit: 'installs', used: 1, max: 1, plan: 'Pro' } }) }
      : fetch(url, init)
  await startSignIn(w.gh)
  await w.advance(5_000)
  await settle()
  expect(await w.gh.state.auth.get()).toEqual({ status: 'out', error: 'Limit reached: installs. 1 of 1 used. The Pro plan lifts it. (trace t)' })
})
