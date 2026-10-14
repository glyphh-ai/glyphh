import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import * as A from '../hooks/glyphh/actions'
import { isLinkable } from '../hooks/glyphh/ui'
import { HOME, fakeHost } from './fake-host'

async function signedInHost(surface: 'desktop' | 'terminal' = 'desktop') {
  const w = fakeHost({ surface })
  await signedIn(w.gh, 'i1', w.server.TOKEN)
  return w
}

test('signed out: opening a section loads nothing', async () => {
  const w = fakeHost()
  await A.openSection(w.gh, 'org')
  expect(await w.gh.state.section.get()).toBe('org')
  expect(w.s.calls).toHaveLength(0)
})

test('account: rename, list installs, revoke another, revoke this one signs out', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'account')
  expect((await w.gh.state.lists.get()).installs).toHaveLength(2)
  await A.rename(w.gh, '  Chris T ')
  expect(w.s.name).toBe('Chris T')
  expect(await w.note()).toBe('Name changed.')
  await A.revokeInstall(w.gh, 'i2')
  expect((await w.gh.state.lists.get()).installs?.map(i => i.id)).toEqual(['i1'])
  await A.revokeInstall(w.gh, 'i1')
  expect(await w.gh.state.auth.get()).toEqual({ status: 'out', error: 'This install was revoked.' })
  expect(w.files.has(`${HOME}/.glyphh/install.json`)).toBe(false)
})

test('a revoked token anywhere signs this machine out', async () => {
  const w = await signedInHost()
  w.files.set(`${HOME}/.glyphh/install.json`, JSON.stringify({ install_id: 'i1', token: 'stale' }))
  await A.openSection(w.gh, 'plan')
  expect(await w.gh.state.auth.get()).toEqual({ status: 'out', error: 'This install was signed out. Sign in again.' })
  expect(await w.gh.state.me.get()).toBeNull()
})

test('org: rename, remove a member, send an invite (its link kept to copy), revoke it', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'org')
  expect((await w.gh.state.lists.get()).members).toHaveLength(2)
  await A.renameOrg(w.gh, 'Glyphh AI')
  expect(w.s.orgName).toBe('Glyphh AI')
  await A.removeMember(w.gh, 'u2')
  expect((await w.gh.state.lists.get()).members?.map(m => m.user_id)).toEqual(['u1'])
  await A.sendInvite(w.gh, 'new@example.com')
  expect(await w.gh.state.inviteLink.get()).toBe('https://glyphh.test/join?t=abc')
  expect(await w.note()).toBe('Invite sent to new@example.com. Copy the link below to share it.')
  expect((await w.gh.state.lists.get()).invites).toHaveLength(1)
  await A.revokeInvite(w.gh, 'inv-1')
  expect((await w.gh.state.lists.get()).invites).toHaveLength(0)
})

test('org: a member is refused admin writes, and told so', async () => {
  const w = await signedInHost()
  w.s.role = 'member'
  await A.renameOrg(w.gh, 'Mine now')
  expect(await w.gh.state.note.get()).toEqual({ text: 'Admins only. (trace tr-1)', isError: true })
  expect(w.s.orgName).toBe('Glyphh')
})

test('plan: /v1/me and the plans list load', async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'plan')
  expect((await w.gh.state.me.get())?.plan).toMatchObject({ name: 'Free' })
  expect((await w.gh.state.lists.get()).plans?.map(p => p.name)).toEqual(['Free', 'Pro'])
  expect(w.s.calls.find(c => c.path === '/v1/plans')?.bearer).toBeUndefined()
})

test('billing: Stripe pages open in the browser pane on the desktop, as links in a terminal', async () => {
  const w = await signedInHost('desktop')
  await A.checkout(w.gh, 'Pro', 2)
  expect(w.s.calls.at(-1)).toMatchObject({ path: '/v1/billing/checkout', body: { plan: 'Pro', seats: 2 } })
  expect(w.opened).toEqual(['https://checkout.stripe.test/c1'])
  expect(await w.gh.state.note.get()).toMatchObject({ text: 'Checkout opened in the browser pane.', link: 'https://checkout.stripe.test/c1' })

  const t = await signedInHost('terminal')
  await A.portal(t.gh)
  expect(t.opened).toEqual([])
  expect(await t.gh.state.note.get()).toMatchObject({ text: "Stripe's billing portal: open this link.", link: 'https://billing.stripe.test/p1' })
  await A.changePlan(t.gh, 'Pro')
  expect(t.s.calls.some(c => c.path === '/v1/billing/plan' && c.body.plan === 'Pro')).toBe(true)
  await A.changeSeats(t.gh, 'three')
  expect(await t.gh.state.note.get()).toMatchObject({ isError: true })
  await A.changeSeats(t.gh, '3')
  expect(t.s.calls.at(-2)).toMatchObject({ path: '/v1/billing/seats', body: { seats: 3 } })
})

test('links: https and localhost draw as links, anything else as text (a bad Link refuses the panel)', () => {
  expect(isLinkable('https://checkout.stripe.com/c/1')).toBe(true)
  expect(isLinkable('http://localhost:8080/v1/device?code=X')).toBe(true)
  expect(isLinkable('http://glyphh.lan/v1/device')).toBe(false)
  expect(isLinkable('javascript:alert(1)')).toBe(false)
})
