import { expect, test } from 'claude-code/testing'

import { signedIn } from '../hooks/glyphh/account'
import * as A from '../hooks/glyphh/actions'
import { ADA_CONTRACT, adaLines, tooNew } from '../hooks/glyphh/ada'
import { usageLines } from '../hooks/glyphh/sections/plan'
import { cloudLimits, count, money, priceText } from '../hooks/glyphh/shape'
import { isLinkable } from '../hooks/glyphh/ui'
import { HOME, fakeHost } from './fake-host'
import { ADA_LATER, PLANS } from './fake-server'

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

test('a revoked token anywhere signs this device out', async () => {
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
  expect((await w.gh.state.lists.get()).plans?.map(p => p.name)).toEqual(['Free', 'Basic', 'Pro', 'Team', 'Enterprise'])
  expect(w.s.calls.find(c => c.path === '/v1/plans')?.bearer).toBeUndefined()
})

test('plan: each plan by its price and Ada Cloud caps; Enterprise by contract, never a rate', () => {
  expect(PLANS.map(p => `${p.name} · ${priceText(p)} · ${cloudLimits(p)}`)).toEqual([
    'Free · $0 · 1,000 precedents · 5,000 reads a month · none past the month',
    'Basic · $20/month · 10,000 precedents · 50,000 reads a month · then $1 per 10,000',
    'Pro · $99/month · 100,000 precedents · 1,000,000 reads a month · then $1 per 10,000',
    'Team · $299/month · 1,000,000 precedents · 5,000,000 reads a month · then $1 per 10,000',
    'Enterprise · By contract · by contract',
  ])
  expect(cloudLimits({ name: 'Old', price_cents: 0 })).toBe('by contract')
  expect(money(1234)).toBe('$12.34')
  expect(count(1000000)).toBe('1,000,000')
})

test("plan: the org's Ada Cloud use: precedents and reads of the plan's, the reset, reads past the month", async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'plan')
  const at = (name: string) => PLANS.find(p => p.name === name)
  expect(usageLines(await w.gh.state.me.get(), at('Free'))).toEqual([
    'Precedents: 432 of 1,000, in 2 models',
    'Reads 2026-10: 1,234 of 5,000',
    "The month's reads start again 2026-11-01.",
  ])

  w.s.plan = 'Basic'
  w.s.reads = 62000
  await A.openSection(w.gh, 'plan')
  expect(usageLines(await w.gh.state.me.get(), at('Basic'))[1]).toBe('Reads 2026-10: 62,000 of 50,000; 12,000 past it, metered at $1 per 10,000')

  w.s.plan = 'Enterprise'
  await A.openSection(w.gh, 'plan')
  expect(usageLines(await w.gh.state.me.get(), at('Enterprise')).slice(0, 2)).toEqual([
    'Precedents: 432 (by contract), in 2 models',
    'Reads 2026-10: 62,000 (by contract)',
  ])
  expect(usageLines({ plan: { name: 'Free' } })).toEqual(['Ada Cloud usage: not available yet.'])
})

test("plan: the org's models by Ada version, the latest stable named, a beta labelled", async () => {
  const w = await signedInHost()
  await A.openSection(w.gh, 'plan')
  expect(adaLines(await w.gh.state.me.get())).toEqual([
    { text: 'Ada versions: the latest stable is ada-1-0.' },
    { text: 'ada-1-1-beta · Beta, opt in by name · 1 model' },
    { text: 'ada-1-0 · Stable, the default · 2 models' },
  ])
})

test('plan: a deprecated Ada says when it ends and what to do; a retired one without models is left out', async () => {
  const w = await signedInHost()
  w.s.ada = ADA_LATER
  await A.openSection(w.gh, 'plan')
  expect(adaLines(await w.gh.state.me.get())).toEqual([
    { text: 'Ada versions: the latest stable is ada-1-1.' },
    { text: 'ada-1-1 · Stable, the default · 1 model' },
    { text: 'ada-1-0 · Deprecated, ends 2027-04-21 · 2 models' },
    {
      text: '2 models on ada-1-0: it answers until 2027-04-21, then they move to ada-1-1 by themselves. Upgrade sooner: ask Claude to backtest ada-1-1 and upgrade.',
      tone: 'warning',
    },
  ])
  const closed = { ...ADA_LATER, versions: [{ ...ADA_LATER.versions[0], name: 'ada-1-2-beta', status: 'beta', beta: true, open: false, models: 0 }] }
  expect(adaLines({ cloud: { ada: closed } })[1]).toEqual({ text: 'ada-1-2-beta · Beta, closed to new models · 0 models' })
})

test('plan: a server of a newer contract is said plainly, with how to update; none yet is said too', async () => {
  expect(ADA_CONTRACT).toBe(5)
  const w = await signedInHost()
  w.s.ada = { ...ADA_LATER, contract: 6 }
  await A.openSection(w.gh, 'plan')
  expect(adaLines(await w.gh.state.me.get())).toEqual([
    { text: 'Ada Cloud speaks contract 6; this plugin speaks contract 5. Update it: /plugin update glyphh@glyphh, then reload.', tone: 'error' },
  ])
  expect(tooNew(5)).toBeUndefined()
  expect(tooNew('4')).toBeUndefined()
  w.s.ada = null
  await A.openSection(w.gh, 'plan')
  expect(adaLines(await w.gh.state.me.get())).toEqual([{ text: 'Ada versions: not available yet.', tone: 'dim' }])
})

test('billing: Stripe pages open in the browser pane on the desktop, as links in a terminal', async () => {
  const w = await signedInHost('desktop')
  await A.checkout(w.gh, 'Pro')
  expect(w.s.calls.at(-1)).toMatchObject({ path: '/v1/billing/checkout', body: { plan: 'Pro' } })
  expect(Object.keys(w.s.calls.at(-1)!.body)).toEqual(['plan']) // never seats
  expect(w.opened).toEqual(['https://checkout.stripe.test/c1'])
  expect(await w.gh.state.note.get()).toMatchObject({ text: 'Checkout opened in the browser pane.', link: 'https://checkout.stripe.test/c1' })

  const t = await signedInHost('terminal')
  await A.portal(t.gh)
  expect(t.opened).toEqual([])
  expect(await t.gh.state.note.get()).toMatchObject({ text: "Stripe's billing portal: open this link.", link: 'https://billing.stripe.test/p1' })
})

test("billing: change plan once subscribed; the server's refusals are said as it says them", async () => {
  const w = await signedInHost('terminal')
  await A.changePlan(w.gh, 'Team')
  expect(await w.gh.state.note.get()).toEqual({ text: "Your org isn't subscribed: start with checkout. (trace tr-1)", isError: true })
  w.s.billingStatus = 'active'
  w.s.plan = 'Pro'
  await A.checkout(w.gh, 'Team')
  expect(await w.gh.state.note.get()).toMatchObject({ text: 'Your org is already subscribed: change plan instead. (trace tr-1)', isError: true })
  await A.changePlan(w.gh, 'Team')
  expect(w.s.calls.some(c => c.path === '/v1/billing/plan' && c.body.plan === 'Team')).toBe(true)
  expect(w.s.plan).toBe('Team')
  expect((await w.gh.state.me.get())?.plan).toMatchObject({ name: 'Team' })
  w.s.plan = 'Enterprise'
  await A.changePlan(w.gh, 'Pro')
  expect(await w.gh.state.note.get()).toMatchObject({ text: 'Your Enterprise plan is by contract: talk to us at sales@glyphh.ai. (trace tr-1)', isError: true })
})

test('billing: Enterprise is Talk to us: the sales address, copied, never a checkout', async () => {
  const w = await signedInHost()
  const before = w.s.calls.length
  await A.talkToUs(w.gh)
  expect(w.s.calls).toHaveLength(before)
  expect(w.copied).toEqual(['sales@glyphh.ai'])
  expect(await w.note()).toBe('Enterprise is by contract: write to sales@glyphh.ai (copied).')
})

test('links: https and localhost draw as links, anything else as text (a bad Link refuses the panel)', () => {
  expect(isLinkable('https://checkout.stripe.com/c/1')).toBe(true)
  expect(isLinkable('http://localhost:8080/v1/device?code=X')).toBe(true)
  expect(isLinkable('http://glyphh.lan/v1/device')).toBe(false)
  expect(isLinkable('javascript:alert(1)')).toBe(false)
})
