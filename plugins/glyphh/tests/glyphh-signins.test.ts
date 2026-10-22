import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import { FINISH, addIdentity, linkedProviders, refreshIdentities, removeIdentity } from '../hooks/glyphh/identities'
import { fakeHost } from './fake-host'

async function signedInHost(surface: 'desktop' | 'terminal' = 'desktop') {
  const w = fakeHost({ surface })
  await signedIn(w.gh, 'i1', w.server.TOKEN)
  return w
}

const linked = async (w: ReturnType<typeof fakeHost>) => linkedProviders(await w.gh.state.me.get())

test('sign-ins: the linked providers come from /v1/me', async () => {
  const w = await signedInHost()
  expect(await linked(w)).toEqual(['google'])
  expect(linkedProviders({ user: { providers: ['github'] } })).toEqual(['github'])
  expect(linkedProviders(null)).toEqual([])
})

test('sign-ins: Add opens the provider page in the browser pane; Refresh reloads /v1/me', async () => {
  const w = await signedInHost('desktop')
  await addIdentity(w.gh, 'github')
  expect(w.s.calls.at(-1)).toMatchObject({ method: 'POST', path: '/v1/me/identities', body: { provider: 'github' } })
  expect(w.opened).toEqual(['https://accounts.github.test/auth?link=1'])
  expect(await w.gh.state.note.get()).toEqual({ text: FINISH, isError: false, link: 'https://accounts.github.test/auth?link=1' })
  w.s.providers.push('github') // linking finished in the browser
  await refreshIdentities(w.gh)
  expect(w.s.calls.at(-1)).toMatchObject({ method: 'GET', path: '/v1/me' })
  expect(await linked(w)).toEqual(['google', 'github'])
})

test('sign-ins: in a terminal, Add shows the link instead', async () => {
  const w = await signedInHost('terminal')
  await addIdentity(w.gh, 'github')
  expect(w.opened).toEqual([])
  expect(await w.gh.state.note.get()).toEqual({
    text: `Open this link to add GitHub. ${FINISH}`,
    isError: false,
    link: 'https://accounts.github.test/auth?link=1',
  })
})

test('sign-ins: adding one already linked shows the conflict', async () => {
  const w = await signedInHost()
  await addIdentity(w.gh, 'google')
  expect(w.opened).toEqual([])
  expect(await w.gh.state.note.get()).toEqual({ text: 'google is already linked. (trace tr-1)', isError: true })
})

test('sign-ins: Remove deletes one; the last one is refused with the server message', async () => {
  const w = await signedInHost()
  w.s.providers = ['github', 'google']
  await removeIdentity(w.gh, 'github')
  expect(w.s.calls.find(c => c.method === 'DELETE')).toMatchObject({ path: '/v1/me/identities/github' })
  expect(await linked(w)).toEqual(['google'])
  expect(await w.note()).toBe('GitHub removed.')
  await removeIdentity(w.gh, 'google')
  expect(await w.gh.state.note.get()).toEqual({ text: 'You need at least one way to sign in. (trace tr-1)', isError: true })
  expect(w.s.providers).toEqual(['google'])
})
