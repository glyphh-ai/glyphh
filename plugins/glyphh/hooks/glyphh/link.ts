// Linking this machine's rrotor to Glyphh: the server issues the local
// runtime's token to the install that signed in here (POST /v1/runtime/local,
// rotated each time), rrotor takes it (PUT /v1/runtime/token) and connects out.
// Linked, it shows on the platform's Runtimes page, its apps reach the
// organisation's catalogue, and it gets the organisation's licence key.
import type { Json } from '../../types'
import { ApiError, api, describe, readInstall } from './api'
import type { Host } from './host'
import { RROTOR_URL, rrotorToken } from './rrotor'

/** What rrotor says of itself at GET /v1/health, as far as the link goes. */
export type RrotorHealth =
  | { status: 'none' }
  | { status: 'down' }
  | { status: 'up'; version: string; runtime_id: string | null; link: string }

const LINK_WAIT_MS = 20_000
const LINK_POLL_MS = 1_000

async function rrotorCall(gh: Host, token: string, method: string, path: string, body?: unknown): Promise<Json> {
  let r
  try {
    r = await gh.http.fetch(`${RROTOR_URL}${path}`, {
      method,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('E_NETWORK', `rrotor is not answering at ${RROTOR_URL}: start it ("start rrotor", the rrotor skill).`, 0)
  }
  let parsed: unknown
  try {
    parsed = r.text.trim() ? JSON.parse(r.text) : {}
  } catch {
    throw new ApiError('E_BAD_REPLY', `rrotor's answer to ${method} ${path} is not JSON.`, r.status)
  }
  if (!r.ok) {
    const err = (parsed as { error?: { code?: unknown; message?: unknown } }).error
    throw new ApiError(String(err?.code ?? `E_HTTP_${r.status}`), String(err?.message ?? `rrotor refused ${method} ${path} (HTTP ${r.status}).`), r.status)
  }
  return parsed as Json
}

/** Where this machine's rrotor stands: none installed, not running, or up with its link state. */
export async function rrotorHealth(gh: Host): Promise<RrotorHealth> {
  const token = await rrotorToken(gh)
  if (!token) return { status: 'none' }
  try {
    const h = await rrotorCall(gh, token, 'GET', '/v1/health')
    const link = (h.link ?? {}) as Json
    return { status: 'up', version: String(h.version ?? ''), runtime_id: h.runtime_id ? String(h.runtime_id) : null, link: String(link.state ?? 'off') }
  } catch (err) {
    if (err instanceof ApiError && err.code === 'E_NETWORK') return { status: 'down' }
    throw err
  }
}

export const isLinked = (h: RrotorHealth) => h.status === 'up' && h.link === 'online'

/** The one line the Account section shows for it. */
export function linkLine(h: RrotorHealth): string {
  if (h.status === 'none') return 'No rrotor on this machine: ask Claude to "install rrotor".'
  if (h.status === 'down') return 'rrotor not running: ask Claude to "start rrotor".'
  switch (h.link) {
    case 'online': return `Linked as ${h.runtime_id} (rrotor ${h.version})`
    case 'no_token': return `Not linked (rrotor ${h.version})`
    case 'off': return `Link off (rrotor ${h.version})`
    case 'connecting':
    case 'backoff':
    case 'follower': return `Linking… (${h.link}, rrotor ${h.version})`
    default: return `Link ${h.link.replace(/_/g, ' ')} (rrotor ${h.version})`
  }
}

/** The link, made or made again: the server rotates the token, rrotor takes it, and we wait for it to connect. */
export async function linkRrotor(gh: Host): Promise<string> {
  if (!(await readInstall(gh))) throw new ApiError('E_UNAUTHORIZED', 'Sign in to Glyphh first: /glyphh signin', 401)
  const token = await rrotorToken(gh)
  if (!token) throw new ApiError('E_NO_RROTOR', 'No rrotor on this machine: ask Claude to "install rrotor" first (the rrotor skill).', 0)
  const before = await rrotorHealth(gh)
  if (before.status === 'down') throw new ApiError('E_NETWORK', `rrotor is not answering at ${RROTOR_URL}: start it ("start rrotor", the rrotor skill).`, 0)
  const issued = await api<Json>(gh, 'POST', '/v1/runtime/local')
  const runtimeId = String(issued.runtime_id ?? '')
  const runtimeToken = String(issued.token ?? '')
  if (!runtimeId || !runtimeToken) throw new ApiError('E_BAD_REPLY', "The server's answer named no runtime token.", 200)
  await rrotorCall(gh, token, 'PUT', '/v1/runtime/token', { runtime_id: runtimeId, token: runtimeToken })
  const waited = await gh.clock.now()
  for (;;) {
    const h = await rrotorHealth(gh)
    if (isLinked(h)) return `Linked to Glyphh as ${runtimeId}: it shows on the platform's Runtimes page, and its apps reach your organisation's catalogue.`
    if (h.status === 'up' && !['connecting', 'backoff', 'no_token', 'follower'].includes(h.link)) {
      return `rrotor took the token but the link ${h.link.replace(/_/g, ' ')}: check the container's log.`
    }
    if ((await gh.clock.now()) - waited >= LINK_WAIT_MS) {
      return `rrotor took the token (${runtimeId}) and is still connecting; the platform shows it once it is online.`
    }
    await new Promise<void>(resolve => gh.clock.after(LINK_POLL_MS, resolve))
  }
}

/** `/glyphh link`: the outcome as a line, a refusal in the server's or rrotor's words. */
export async function linkFromCommand(gh: Host): Promise<{ text: string; isError: boolean }> {
  try {
    return { text: await linkRrotor(gh), isError: false }
  } catch (err) {
    return { text: describe(err), isError: true }
  }
}
