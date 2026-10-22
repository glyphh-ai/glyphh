// The install's lifetime on this device: signed in (install.json), the
// account as the server says (/v1/me), signed out (the file removed).

import type { AuthState, Json } from '../../types'
import { ApiError, api, describe, readInstall } from './api'
import { glyphhPath, removeFile, writeSecret } from './home'
import { clearAccount, say } from './state'
import type { Host } from './host'

export async function loadMe(gh: Host): Promise<Json> {
  const body = await api(gh, 'GET', '/v1/me')
  await gh.state.me.set(() => body)
  return body
}

/** The token arrived: kept 0600, then the account is fetched. */
export async function signedIn(gh: Host, installId: string, token: string) {
  const path = await glyphhPath(gh, 'install.json')
  if (!path) throw new Error('HOME is not set: nowhere to keep the sign-in')
  await writeSecret(gh, path, { install_id: installId, token })
  await gh.state.auth.set((): AuthState => ({ status: 'in', install_id: installId }))
  await say(gh, 'Signed in.')
  await loadMe(gh).catch(err => say(gh, describe(err), true))
}

/** This device forgets the install: install.json goes (and license.json,
 *  left by plugins before 1.1.5). */
export async function forget(gh: Host, error?: string) {
  for (const name of ['install.json', 'license.json']) {
    const path = await glyphhPath(gh, name)
    if (path) await removeFile(gh, path).catch(() => undefined)
  }
  await clearAccount(gh, error)
}

export async function signOut(gh: Host) {
  await api(gh, 'POST', '/v1/sign-out').catch(() => undefined) // revoked or unreachable: forget anyway
  await forget(gh)
  await say(gh, 'Signed out.')
}

/** At session start: signed in when install.json holds a token. `wait`
 *  awaits the account too (/glyphh, after a sign-in from the card). */
export async function initAccount(gh: Host, wait = false) {
  const install = await readInstall(gh)
  if (!install) return
  await gh.state.auth.set((): AuthState => ({ status: 'in', install_id: install.install_id }))
  if (wait) await refresh(gh)
  else void refresh(gh)
}

/** The account again; a revoked install signs this device out. */
export async function refresh(gh: Host) {
  try {
    await loadMe(gh)
  } catch (err) {
    await failed(gh, err)
  }
}

/** A refusal shown in the panel; 401 means this install was revoked. */
export async function failed(gh: Host, err: unknown) {
  if (err instanceof ApiError && err.status === 401) {
    await forget(gh, 'This install was signed out. Sign in again.')
    return
  }
  await say(gh, describe(err), true)
}

/** A panel action: runs, says what it did, or why not. */
export async function act(gh: Host, done: string | undefined, fn: () => Promise<unknown>) {
  try {
    await fn()
    if (done) await say(gh, done)
  } catch (err) {
    await failed(gh, err)
  }
}
