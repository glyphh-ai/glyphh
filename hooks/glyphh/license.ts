// license.json: GET /v1/license, its Ed25519 signature checked against
// GET /v1/license/key before it is kept. What it gates locally: RPA.
//
// Accepted shapes (the server's choice, any one):
//   { token: "<header>.<payload>.<sig>" }                 compact JWS, EdDSA
//   { payload: "<the JSON text signed>", signature }      signature over payload's bytes
//   { license: {...}, signature }                         signature over the canonical JSON
//                                                         (keys sorted, no spaces, \u escapes)
// The key: { key | public_key }, raw 32 bytes in base64 or base64url, or PEM
// (SPKI), or a JWK { kty: "OKP", crv: "Ed25519", x } (alone or in `keys`).

import type { Json, LicenseInfo } from '../../types'
import { api } from './api'
import { verify } from './ed25519'
import { glyphhPath, readJson, writeJson } from './home'
import type { Host } from './host'

const enc = new TextEncoder()

export function fromBase64(text: string): Uint8Array {
  const b64 = text.trim().replace(/-/g, '+').replace(/_/g, '/').replace(/\s+/g, '')
  const bin = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4))
  return Uint8Array.from(bin, c => c.charCodeAt(0))
}

/** Python's json.dumps(v, sort_keys=True, separators=(",", ":")). */
export function canonical(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`
  if (v && typeof v === 'object') {
    const keys = Object.keys(v).sort()
    return `{${keys.map(k => `${canonical(k)}:${canonical((v as Json)[k])}`).join(',')}}`
  }
  if (typeof v === 'string') return JSON.stringify(v).replace(/[\u007f-￿]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`)
  return JSON.stringify(v)
}

export function publicKey(body: Json): Uint8Array {
  const jwk = (Array.isArray(body.keys) ? body.keys[0] : body) as Json
  const raw = String(body.key ?? body.public_key ?? jwk.x ?? '')
  if (raw.includes('BEGIN')) return fromBase64(raw.replace(/-----[^-]+-----/g, '')).slice(-32)
  const bytes = fromBase64(raw)
  return bytes.length > 32 ? bytes.slice(-32) : bytes
}

/** What was signed, the signature and the claims, from any accepted shape. */
export function signedParts(body: Json): { message: Uint8Array; signature: Uint8Array; claims: Json } {
  if (typeof body.token === 'string') {
    const [gh, p, s] = body.token.split('.')
    if (!gh || !p || !s) throw new Error('license token is not a JWS')
    const claims = JSON.parse(new TextDecoder().decode(fromBase64(p))) as Json
    return { message: enc.encode(`${gh}.${p}`), signature: fromBase64(s), claims }
  }
  const signature = fromBase64(String(body.signature ?? ''))
  if (typeof body.payload === 'string') return { message: enc.encode(body.payload), signature, claims: JSON.parse(body.payload) as Json }
  if (body.license && typeof body.license === 'object') {
    return { message: enc.encode(canonical(body.license)), signature, claims: body.license as Json }
  }
  throw new Error('no license in the answer')
}

export function toInfo(claims: Json, ok: boolean, error?: string): LicenseInfo {
  const plan = claims.plan as Json | string | undefined
  const exp = claims.expires_at ?? claims.exp
  return {
    ok,
    error,
    plan: typeof plan === 'string' ? plan : plan ? String(plan.name ?? '') : undefined,
    features: (claims.features ?? (plan as Json)?.features ?? {}) as Record<string, boolean>,
    limits: (claims.limits ?? (plan as Json)?.limits ?? {}) as Record<string, number | null>,
    expires_at: typeof exp === 'number' ? new Date(exp * 1000).toISOString() : (exp as string | undefined),
  }
}

/** Checks a license answer against a key answer; expired counts as not ok. */
export async function check(body: Json, keyBody: Json, now: number): Promise<LicenseInfo> {
  let parts
  try {
    parts = signedParts(body)
  } catch (err) {
    return toInfo({}, false, String((err as Error).message))
  }
  const good = await verify(publicKey(keyBody), parts.message, parts.signature).catch(() => false)
  const info = toInfo(parts.claims, good, good ? undefined : 'signature does not check out')
  if (good && info.expires_at && Date.parse(info.expires_at) <= now) return { ...info, ok: false, error: 'expired' }
  return info
}

/** Fetches, checks and keeps the license; a bad one is never written. */
export async function refreshLicense(gh: Host): Promise<LicenseInfo> {
  const [body, keyBody] = await Promise.all([api(gh, 'GET', '/v1/license'), api(gh, 'GET', '/v1/license/key')])
  const info = await check(body, keyBody, await gh.clock.now())
  if (info.ok) {
    const path = await glyphhPath(gh, 'license.json')
    if (path) await writeJson(gh, path, { answer: body, key: keyBody })
  }
  await gh.state.license.set(() => info)
  return info
}

/** The kept license, checked again with the key kept beside it (offline:
 *  a local check keeps honest people honest; the server enforces limits). */
export async function loadLicense(gh: Host): Promise<LicenseInfo | null> {
  const kept = await readJson<{ answer?: Json; key?: Json }>(await glyphhPath(gh, 'license.json'), gh)
  if (!kept?.answer || !kept.key) return null
  const info = await check(kept.answer, kept.key, await gh.clock.now())
  await gh.state.license.set(() => info)
  return info
}

/** Whether the license allows a feature (`rpa`). No license, no feature. */
export const allows = (info: LicenseInfo | null, feature: string) => info?.ok === true && info.features[feature] === true
