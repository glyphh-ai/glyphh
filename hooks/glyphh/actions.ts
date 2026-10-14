// What the Account, Org, Plan and Billing sections do: each reads or writes
// the API, then reloads what it changed. Errors land in the panel's note.
import type { RenderSurface } from 'claude-code'

import type { GlyphhSection, Json } from '../../types'
import { api, listOf } from './api'
import { act, forget, loadMe } from './account'
import { openUrl } from './open'
import { say, setList } from './state'
import type { Host } from './host'

const enc = encodeURIComponent

const LOADERS: Record<GlyphhSection, (gh: Host) => Promise<unknown>> = {
  account: gh => api(gh, 'GET', '/v1/installs').then(b => setList(gh, 'installs', listOf(b, 'installs'))),
  org: async gh => {
    await api(gh, 'GET', '/v1/org').then(b => setList(gh, 'org', [b]))
    await api(gh, 'GET', '/v1/org/members').then(b => setList(gh, 'members', listOf(b, 'members')))
    await api(gh, 'GET', '/v1/org/invites').then(b => setList(gh, 'invites', listOf(b, 'invites')))
  },
  plan: gh => api(gh, 'GET', '/v1/plans', undefined, { auth: false }).then(b => setList(gh, 'plans', listOf(b, 'plans'))),
  billing: gh => api(gh, 'GET', '/v1/plans', undefined, { auth: false }).then(b => setList(gh, 'plans', listOf(b, 'plans'))),
  workspaces: gh => api(gh, 'GET', '/v1/workspaces').then(b => setList(gh, 'workspaces', listOf(b, 'workspaces'))),
}

/** Opens a section and loads what it shows (signed out: nothing to load). */
export async function openSection(gh: Host, id: GlyphhSection) {
  await gh.state.section.set(() => id)
  if ((await gh.state.auth.get()).status !== 'in') return
  await act(gh, undefined, async () => {
    await loadMe(gh)
    await LOADERS[id](gh)
  })
}

const reload = (gh: Host) => LOADERS.account(gh)

export const rename = (gh: Host, name: string) =>
  act(gh, 'Name changed.', async () => {
    await api(gh, 'PATCH', '/v1/me', { name: name.trim() })
    await loadMe(gh)
  })

export const revokeInstall = (gh: Host, id: string) =>
  act(gh, 'Install revoked.', async () => {
    await api(gh, 'DELETE', `/v1/installs/${enc(id)}`)
    const a = await gh.state.auth.get()
    if (a.status === 'in' && a.install_id === id) return forget(gh, 'This install was revoked.')
    await reload(gh)
  })

export const renameOrg = (gh: Host, name: string) =>
  act(gh, 'Org renamed.', async () => {
    await api(gh, 'PATCH', '/v1/org', { name: name.trim() })
    await loadMe(gh)
    await LOADERS.org(gh)
  })

export const removeMember = (gh: Host, userId: string) =>
  act(gh, 'Member removed.', async () => {
    await api(gh, 'DELETE', `/v1/org/members/${enc(userId)}`)
    await loadMe(gh)
    await LOADERS.org(gh)
  })

export const sendInvite = (gh: Host, email: string) =>
  act(gh, undefined, async () => {
    const r = await api<Json>(gh, 'POST', '/v1/org/invites', { email: email.trim() })
    const link = String(r.link ?? r.url ?? r.invite_url ?? '')
    await gh.state.inviteLink.set(() => link || null)
    await say(gh, `Invite sent to ${email.trim()}.${link ? ' Copy the link below to share it.' : ''}`)
    await LOADERS.org(gh)
  })

export const revokeInvite = (gh: Host, id: string) =>
  act(gh, 'Invite revoked.', async () => {
    await api(gh, 'DELETE', `/v1/org/invites/${enc(id)}`)
    await LOADERS.org(gh)
  })

/** A Stripe page from the server: opened in the browser pane, or linked. */
async function stripePage(gh: Host, path: string, body: unknown, what: string, surface?: RenderSurface) {
  await act(gh, undefined, async () => {
    const r = await api<Json>(gh, 'POST', path, body)
    const url = String(r.url ?? '')
    if (!url) return say(gh, `${what}: done.`)
    const opened = await openUrl(gh, url, surface)
    await say(gh, opened ? `${what} opened in the browser pane.` : `${what}: open this link.`, false, url)
  })
}

export const checkout = (gh: Host, plan: string, seats: number, surface?: RenderSurface) =>
  stripePage(gh, '/v1/billing/checkout', { plan, seats }, 'Checkout', surface)

export const portal = (gh: Host, surface?: RenderSurface) =>
  stripePage(gh, '/v1/billing/portal', undefined, "Stripe's billing portal", surface)

export const changePlan = (gh: Host, plan: string, surface?: RenderSurface) =>
  stripePage(gh, '/v1/billing/plan', { plan }, `Plan changed to ${plan}`, surface).then(() => loadMe(gh).catch(() => undefined))

export const changeSeats = (gh: Host, text: string) => {
  const seats = Number(text.trim())
  if (!Number.isInteger(seats) || seats < 1) return say(gh, 'Seats must be a whole number, 1 or more.', true)
  return act(gh, `Seats set to ${seats}.`, async () => {
    await api(gh, 'POST', '/v1/billing/seats', { seats })
    await loadMe(gh)
  })
}
