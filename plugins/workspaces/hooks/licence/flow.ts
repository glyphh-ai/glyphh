// Copied from shared/licence/flow.ts by scripts/sync-shared.mjs: edit it there.
// The licence's life: the trial's first day, the stored licence checked at
// each session start, the purchase (checkout opened, then the site asked
// every few seconds until it answers a licence), and a licence key pasted in.
// It works on Deps, closures over `$` that ./hooks.tsx hands it.
import type { Timer } from 'claude-code'

import type { LicenceState } from '../../types'
import { MOD, PAYMENT_LINK, PRODUCT } from './config.ts'
import { POLL_MS, SITE, WAIT_MS } from './site.ts'

export type Deps = {
  store: {
    get(key: string): Promise<unknown>
    set(key: string, value: string | number): Promise<void>
    delete(key: string): Promise<void>
  }
  state: { get(): Promise<LicenceState>; set(fn: (s: LicenceState) => LicenceState): Promise<void> }
  now(): Promise<number>
  /** Runs `fn` every `ms` until cancelled. */
  every(ms: number, fn: () => Promise<void>): Timer
  /** Whether a licence is this mod's, signed by the site. */
  check(licence: string): Promise<boolean>
  fetch(url: string): Promise<{ ok: boolean; text: string }>
  /** Opens a page in the person's browser; false when it could not. */
  open(url: string): Promise<boolean>
  copy(text: string): Promise<boolean>
  toast(text: string): void
  log(text: string): void
}

const KEY = { install: 'install', licence: 'licence', trial: 'trialStartedAt' } as const

let poll: Timer | null = null

function stopPolling() {
  poll?.cancel()
  poll = null
}

/** This install's id: made once, kept in the store. */
async function installId(d: Deps): Promise<string> {
  const kept = await d.store.get(KEY.install)
  if (typeof kept === 'string') return kept
  const id = crypto.randomUUID()
  await d.store.set(KEY.install, id)
  return id
}

/** At each session start: the trial's first day (set once), and the stored
 *  licence checked again; one that no longer checks out is dropped. */
export async function start(d: Deps): Promise<void> {
  stopPolling()
  const keptStart = await d.store.get(KEY.trial)
  const trialStartedAt = typeof keptStart === 'number' ? keptStart : await d.now()
  if (keptStart !== trialStartedAt) await d.store.set(KEY.trial, trialStartedAt)
  const kept = await d.store.get(KEY.licence)
  let licence: string | null = null
  if (typeof kept === 'string' && (await d.check(kept))) licence = kept
  else if (kept !== undefined) await d.store.delete(KEY.licence)
  await d.state.set(() => ({ licence, trialStartedAt, isWaiting: false, note: null }))
}

/** A licence that checks out is kept and unlocks the mod; false otherwise. */
export async function accept(d: Deps, raw: string): Promise<boolean> {
  const licence = raw.trim()
  if (!(await d.check(licence))) return false
  stopPolling()
  await d.store.set(KEY.licence, licence)
  await d.state.set(s => ({ ...s, licence, isWaiting: false, note: null }))
  return true
}

/** Opens checkout for this install, then waits for the site to say it is paid. */
export async function buy(d: Deps): Promise<void> {
  const install = await installId(d)
  const url = `${PAYMENT_LINK}?client_reference_id=${encodeURIComponent(install)}`
  await d.state.set(s => ({ ...s, isWaiting: true, note: `Finish checkout in your browser: ${PRODUCT} unlocks on its own.` }))
  if (!(await d.open(url))) {
    d.toast((await d.copy(url)) ? 'The checkout link is copied: paste it into your browser.' : `Open this link to buy: ${url}`)
  }
  stopPolling()
  const since = await d.now()
  const timer: Timer = d.every(POLL_MS, () => tick(d, timer, install, since).catch(err => d.log(`${MOD} licence: ${String(err)}`)))
  poll = timer
}

/** Stops waiting for a purchase. */
export async function cancel(d: Deps): Promise<void> {
  stopPolling()
  await d.state.set(s => ({ ...s, isWaiting: false, note: null }))
}

type Answer = { paid?: unknown; licence?: unknown }

function parse(text: string): Answer | null {
  try {
    const body: unknown = JSON.parse(text)
    return body && typeof body === 'object' ? (body as Answer) : null
  } catch {
    return null
  }
}

/** One ask of the site; an answer for a wait that has been stopped is dropped. */
async function tick(d: Deps, timer: Timer, install: string, since: number): Promise<void> {
  if ((await d.now()) - since >= WAIT_MS) {
    stopPolling()
    await d.state.set(s => ({ ...s, isWaiting: false, note: 'No purchase seen in 10 minutes. Press Unlock to try again.' }))
    return
  }
  const res = await d.fetch(`${SITE}/api/license?mod=${MOD}&install=${encodeURIComponent(install)}`).catch(() => null)
  if (poll !== timer || !res?.ok) return
  const body = parse(res.text)
  if (body?.paid !== true || typeof body.licence !== 'string') return
  stopPolling()
  if (await accept(d, body.licence)) d.toast(`${PRODUCT} unlocked. Thank you!`)
  else await d.state.set(s => ({ ...s, isWaiting: false, note: 'The licence the site sent did not check out. Press Unlock to try again.' }))
}
