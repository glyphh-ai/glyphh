// The Glyphh server's API client: JSON under /v1, the install's token as the
// bearer, refusals as {"error": {code, message, trace_id, ...detail}}.

import type { Json } from '../../types'
import { glyphhPath, readJson } from './home'
import type { Host } from './host'
import { count } from './shape'

export const DEFAULT_SERVER = 'https://api.glyphh.ai'

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly detail: Json = {},
    readonly traceId?: string,
  ) {
    super(message)
  }
}

export type Install = { install_id: string; token: string }

export async function serverUrl(gh: Host): Promise<string> {
  const set = await gh.env.server().catch(() => undefined)
  return (set?.trim() || DEFAULT_SERVER).replace(/\/+$/, '')
}

export async function readInstall(gh: Host): Promise<Install | undefined> {
  const found = await readJson<Partial<Install>>(await glyphhPath(gh, 'install.json'), gh)
  return found?.token && found.install_id ? { install_id: found.install_id, token: found.token } : undefined
}

function refusal(status: number, text: string): ApiError {
  let body: unknown
  try {
    body = JSON.parse(text)
  } catch {
    return new ApiError(`E_HTTP_${status}`, text.trim().slice(0, 200) || `HTTP ${status}`, status)
  }
  const err = (body as { error?: unknown })?.error
  if (typeof err === 'string') return new ApiError(err, err, status) // RFC 8628's own shape
  if (err && typeof err === 'object') {
    const { code, message, trace_id, ...detail } = err as Json
    return new ApiError(String(code ?? `E_HTTP_${status}`), String(message ?? code ?? ''), status, detail, trace_id as string | undefined)
  }
  return new ApiError(`E_HTTP_${status}`, `HTTP ${status}`, status)
}

/** One call. `auth: false` for the device flow and the plans list. */
export async function api<T = Json>(
  gh: Host,
  method: string,
  path: string,
  body?: unknown,
  opts: { auth?: boolean } = {},
): Promise<T> {
  const base = await serverUrl(gh)
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.auth !== false) {
    const install = await readInstall(gh)
    if (!install) throw new ApiError('E_UNAUTHORIZED', 'Not signed in.', 401)
    headers.Authorization = `Bearer ${install.token}`
  }
  let r
  try {
    r = await gh.http.fetch(`${base}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError('E_NETWORK', `Cannot reach the Glyphh server at ${base}.`, 0)
  }
  if (!r.ok) throw refusal(r.status, r.text)
  if (!r.text.trim()) return {} as T
  try {
    return JSON.parse(r.text) as T
  } catch {
    throw new ApiError('E_BAD_REPLY', `The server's answer to ${method} ${path} is not JSON.`, r.status)
  }
}

const num = (v: unknown) => (typeof v === 'number' || typeof v === 'string' ? String(v) : undefined)

/** A refusal as a person reads it; a limit names what is used and what lifts it. */
export function describe(err: unknown): string {
  if (!(err instanceof ApiError)) return String(err instanceof Error ? err.message : err)
  const trace = err.traceId ? ` (trace ${err.traceId})` : ''
  if (err.code !== 'E_LIMIT') return `${err.message || err.code}${trace}`
  const d = err.detail
  const used = num(d.used)
  const max = num(d.max)
  const what = num(d.limit ?? d.reason)
  const label = what === 'requests' ? 'reads' : what
  const usage = used !== undefined && max !== undefined ? ` (${count(d.used)} of ${count(d.max)}${label ? ` ${label}` : ''} used)` : ''
  return `${err.message || 'Limit reached.'}${usage}${trace}`
}

/** A list from an answer that is the list itself or holds it under a key. */
export function listOf(body: unknown, ...keys: string[]): Json[] {
  if (Array.isArray(body)) return body as Json[]
  const o = (body ?? {}) as Json
  for (const k of [...keys, 'items', 'data']) if (Array.isArray(o[k])) return o[k] as Json[]
  return []
}
