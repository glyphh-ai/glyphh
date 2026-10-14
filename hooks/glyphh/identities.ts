// The ways a person signs in (Google, GitHub): listed from /v1/me, another
// added in the browser (the server hands back the provider's page), one
// removed while another remains (the server refuses the last).
import type { RenderSurface } from 'claude-code'

import type { Json } from '../../types'
import { act, loadMe } from './account'
import { api } from './api'
import type { Host } from './host'
import { openUrl } from './open'
import { obj, str, userOf } from './shape'
import { say } from './state'

export const PROVIDERS = [
  { id: 'google', label: 'Google' },
  { id: 'github', label: 'GitHub' },
] as const

export type Provider = (typeof PROVIDERS)[number]['id']

export const FINISH = 'Finish in the browser, then press Refresh.'

export const providerLabel = (id: string) => PROVIDERS.find(p => p.id === id)?.label ?? id

/** The linked providers, from `me.providers` (or under `me.user`). */
export function linkedProviders(me: Json | null): string[] {
  const list = obj(me).providers ?? userOf(me).providers
  return Array.isArray(list) ? list.map(p => str(p)).filter(Boolean) : []
}

/** Starts linking: the provider's page opens in the browser pane, or is linked. */
export const addIdentity = (gh: Host, provider: Provider, surface?: RenderSurface) =>
  act(gh, undefined, async () => {
    const r = await api<Json>(gh, 'POST', '/v1/me/identities', { provider })
    const url = str(r.url)
    if (!url) return say(gh, `${providerLabel(provider)}: the server gave no page to open.`, true)
    const opened = await openUrl(gh, url, surface)
    await say(gh, opened ? FINISH : `Open this link to add ${providerLabel(provider)}. ${FINISH}`, false, url)
  })

export const removeIdentity = (gh: Host, provider: string) =>
  act(gh, `${providerLabel(provider)} removed.`, async () => {
    await api(gh, 'DELETE', `/v1/me/identities/${encodeURIComponent(provider)}`)
    await loadMe(gh)
  })

/** /v1/me again, after linking finished in the browser. */
export const refreshIdentities = (gh: Host) => act(gh, 'Refreshed.', () => loadMe(gh))
