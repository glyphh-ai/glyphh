// Sign in by device flow (RFC 8628): ask for a code, show it and its link,
// open the link where there is a browser pane, poll for the install's token.
import type { RenderSurface, Timer } from 'claude-code'

import type { AuthState, Json } from '../../types'
import { ApiError, api, describe } from './api'
import { signedIn } from './account'
import { openUrl, surfaceNow } from './open'
import type { Host } from './host'
import { machineId, type MachineProbe } from './machine'

let timer: Timer | undefined

async function modVersion(gh: Host): Promise<string> {
  try {
    const text = await gh.fs.read(`${gh.pluginRoot}/.claude-plugin/plugin.json`)
    return String((JSON.parse(String(text)) as Json).version ?? '0.0.0')
  } catch {
    return '0.0.0'
  }
}

async function machineName(gh: Host): Promise<string> {
  const r = await gh.process.run(['hostname', '-s']).catch(() => undefined)
  return r?.exitCode === 0 && r.stdout.trim() ? r.stdout.trim() : 'Claude'
}

/** The machine id's sources, through the Host. */
export async function machineProbe(gh: Host): Promise<MachineProbe> {
  return {
    home: await gh.env.home().catch(() => undefined),
    run: argv => gh.process.run(argv),
    read: path => gh.fs.read(path),
    write: (path, text) => gh.fs.write(path, text),
  }
}

function schedule(gh: Host, seconds: number) {
  timer?.cancel()
  timer = gh.clock.after(Math.max(1, seconds) * 1000, () => void poll(gh))
}

export function stopPolling() {
  timer?.cancel()
  timer = undefined
}

/** Starts a sign-in: the code is shown, the link opened on the desktop. */
export async function startSignIn(gh: Host, hint?: RenderSurface): Promise<AuthState> {
  const surface = await surfaceNow(gh, hint)
  const body = {
    name: await machineName(gh),
    surface: surface === 'desktop' ? 'desktop' : 'cli',
    mod_version: await modVersion(gh),
    machine_id: await machineId(await machineProbe(gh)),
  }
  const r = await api(gh, 'POST', '/v1/device/code', body, { auth: false })
  const interval = Number(r.interval ?? 5)
  const state: AuthState = {
    status: 'pending',
    device_code: String(r.device_code),
    user_code: String(r.user_code),
    verification_uri: String(r.verification_uri),
    verification_uri_complete: String(r.verification_uri_complete ?? r.verification_uri),
    interval,
    expires_at: (await gh.clock.now()) + Number(r.expires_in ?? 600) * 1000,
    opened: false,
  }
  await gh.state.auth.set(() => state)
  schedule(gh, interval)
  const opened = await openUrl(gh, state.verification_uri_complete, surface ?? undefined)
  if (opened) await gh.state.auth.set(a => (a.status === 'pending' ? { ...a, opened: true } : a))
  return { ...state, opened }
}

const normal = (code: string) => code.toLowerCase().replace(/^e_/, '')

async function endPending(gh: Host, error: string) {
  stopPolling()
  await gh.state.auth.set((): AuthState => ({ status: 'out', error }))
}

/** One poll; schedules the next while the code is pending. */
export async function poll(gh: Host): Promise<void> {
  const a = await gh.state.auth.get()
  if (a.status !== 'pending') return
  if ((await gh.clock.now()) >= a.expires_at) return endPending(gh, 'The code expired. Sign in again.')
  let code: string
  let err: unknown
  try {
    const r = await api(gh, 'POST', '/v1/device/token', { device_code: a.device_code }, { auth: false })
    if (typeof r.access_token === 'string') {
      stopPolling()
      return signedIn(gh, String(r.install_id ?? ''), r.access_token)
    }
    code = normal(String(r.error ?? 'authorization_pending'))
  } catch (caught) {
    err = caught
    code = caught instanceof ApiError ? normal(caught.code) : 'unknown'
  }
  return answer(gh, a, code, err)
}

async function answer(gh: Host, a: Extract<AuthState, { status: 'pending' }>, code: string, err: unknown) {
  if (code === 'authorization_pending' || code === 'network') return schedule(gh, a.interval)
  if (code === 'slow_down') {
    const interval = a.interval + 5
    await gh.state.auth.set(s => (s.status === 'pending' ? { ...s, interval } : s))
    return schedule(gh, interval)
  }
  if (code === 'expired_token') return endPending(gh, 'The code expired. Sign in again.')
  if (code === 'access_denied') return endPending(gh, 'Sign-in was declined.')
  return endPending(gh, describe(err ?? code))
}

/** After a reload mid sign-in: the timer was dropped, so polling resumes. */
export async function resumePolling(gh: Host) {
  const a = await gh.state.auth.get()
  if (a.status === 'pending') schedule(gh, a.interval)
}
