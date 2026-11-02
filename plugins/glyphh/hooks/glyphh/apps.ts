// The organisation's apps (what Claude made and published to its rrotors: a
// page, a dashboard, a doc, a diagram, a deck, a design; server/docs/specs/
// apps.md): listed from the catalogue by search, page, view and type; opened
// at the rrotor; and for a reviewer approved, rejected or retired. `/glyphh
// publish <file>` publishes one file from this machine to the local rrotor as
// an app, awaiting that review.
import type { RenderSurface } from 'claude-code'

import type { AppsView, Json } from '../../types'
import { act, loadMe } from './account'
import { api, describe, listOf } from './api'
import type { Host } from './host'
import { openUrl } from './open'
import { obj, str } from './shape'
import { publishApp, type AppPublish } from './rrotor'
import { say, setList } from './state'

export const PER_PAGE = 24
export const FIRST_VIEW: AppsView = { q: '', page: 1, state: 'approved', type: '', total: 0, rejecting: null }

/** The reviewer's views beside the published ones. */
export const VIEWS: { id: string; label: string }[] = [
  { id: 'approved', label: 'Published' },
  { id: 'draft', label: 'Awaiting review' },
  { id: 'rejected', label: 'Rejected' },
]

/** The six types as the catalogue keeps them: the card's chip and the filter's word. */
export const TYPES: { id: string; chip: string; filter: string }[] = [
  { id: 'page', chip: 'Page', filter: 'Pages' },
  { id: 'dashboard', chip: 'Dashboard', filter: 'Dashboards' },
  { id: 'doc', chip: 'Doc', filter: 'Docs' },
  { id: 'diagram', chip: 'Diagram', filter: 'Diagrams' },
  { id: 'deck', chip: 'Deck', filter: 'Decks' },
  { id: 'design', chip: 'Design', filter: 'Designs' },
]
export const ALL_TYPES = 'All types'

/** The card's chip: the row's type as a word (a row without one is a page). */
export const typeChip = (a: Json): string => TYPES.find(t => t.id === str(a.type))?.chip ?? 'Page'

/** The filter button's label: the type the view shows, or All types. */
export const typeLabel = (v: AppsView): string => TYPES.find(t => t.id === v.type)?.filter ?? ALL_TYPES

/** The type after this one: All types → Pages → … → Designs → All types. */
export function nextType(type: string): string {
  const i = TYPES.findIndex(t => t.id === type)
  return i < 0 ? TYPES[0]!.id : (TYPES[i + 1]?.id ?? '')
}

export const isReviewer = (me: Json | null): boolean => obj(me).reviewer === true

/** The page the view asks for, from `GET /v1/apps`: the cards and the count. */
export async function loadApps(gh: Host) {
  const v = await gh.state.apps.get()
  const query = new URLSearchParams({ page: String(v.page), per_page: String(PER_PAGE), state: v.state })
  if (v.q) query.set('q', v.q)
  if (v.type) query.set('type', v.type)
  const body = await api<Json>(gh, 'GET', `/v1/apps?${query}`)
  await setList(gh, 'apps', listOf(body, 'apps'))
  const total = typeof body.total === 'number' ? body.total : listOf(body, 'apps').length
  await gh.state.apps.set(s => ({ ...s, total }))
}

const reload = (gh: Host, change: (v: AppsView) => AppsView) =>
  act(gh, undefined, async () => {
    await gh.state.apps.set(change)
    await loadApps(gh)
  })

export const searchApps = (gh: Host, q: string) => reload(gh, v => ({ ...v, q: q.trim(), page: 1 }))

export const turnPage = (gh: Host, by: number) => reload(gh, v => ({ ...v, page: Math.max(1, v.page + by) }))

export const viewApps = (gh: Host, state: string) => reload(gh, v => ({ ...v, state, page: 1, rejecting: null }))

/** The filter button: the next type in the cycle, from page 1. */
export const cycleType = (gh: Host) => reload(gh, v => ({ ...v, type: nextType(v.type), page: 1 }))

/** The last page's number for the count the server gave. */
export const pages = (v: AppsView) => Math.max(1, Math.ceil(v.total / PER_PAGE))

/** "1–24 of 57": what the page shows of the whole. */
export function pageLine(v: AppsView, shown: number): string {
  if (v.total === 0) return 'Nothing here.'
  const from = (v.page - 1) * PER_PAGE + 1
  return `${from}–${from + shown - 1} of ${v.total}`
}

/** The app in the browser pane on the desktop; the link in a terminal. */
export async function openApp(gh: Host, a: Json, surface?: RenderSurface) {
  const url = str(a.url)
  if (!url) return say(gh, 'This app has no address yet.', true)
  const opened = await openUrl(gh, url, surface)
  await say(gh, opened ? `${str(a.title)} opened in the browser pane.` : `${str(a.title)}: open this link.`, false, url)
}

const enc = encodeURIComponent

const review = (gh: Host, id: string, verb: string, done: string, body?: Json) =>
  act(gh, done, async () => {
    await api(gh, 'POST', `/v1/apps/${enc(id)}/${verb}`, body)
    await gh.state.apps.set(v => ({ ...v, rejecting: null }))
    await loadApps(gh)
  })

export const approveApp = (gh: Host, id: string) => review(gh, id, 'approve', 'Approved: its people can open it now.')
export const retireApp = (gh: Host, id: string) => review(gh, id, 'retire', 'Retired: no longer served or listed.')

/** Reject asks for the reason first: the card shows an input until it is given. */
export const askReason = (gh: Host, id: string | null) => gh.state.apps.set(v => ({ ...v, rejecting: id }))

export const rejectApp = (gh: Host, id: string, reason: string) => {
  const why = reason.trim()
  if (!why) return say(gh, 'Say why it is rejected: the person who published it reads the reason.', true)
  return review(gh, id, 'reject', 'Rejected, with the reason.', { reason: why })
}

/** Who published it and when, as the card says it. */
export function publishedLine(a: Json): string {
  const by = obj(a.submitted_by)
  const who = str(by.name || by.email, 'someone')
  const when = str(a.submitted_at).slice(0, 10)
  return `Published by ${who}${when ? ` · ${when}` : ''}`
}

export const rolesLine = (a: Json): string => (Array.isArray(a.roles) && a.roles.length ? a.roles.map(r => str(r)).join(', ') : 'Everyone')

const names = (v: unknown): string[] => (Array.isArray(v) ? v.map(x => str(x)).filter(Boolean) : [])

/** What the app needs (the spec's 4.7), as the platform's card says it: who its functions run as, its CLIs and who
 *  signs them in, its secrets. Null when it needs nothing (no CLIs, no secrets, run as the viewer). */
export function needsLine(a: Json): string | null {
  const clis = names(a.clis)
  const secrets = names(a.secrets)
  const asApp = str(a.run_as) === 'app'
  if (!clis.length && !secrets.length && !asApp) return null
  const parts = [asApp ? 'Runs as the app' : 'Runs as the viewer']
  if (clis.length) parts.push(`${clis.join(', ')} (${asApp ? 'signed in once by an admin' : 'each viewer signs in'})`)
  if (secrets.length) parts.push(`secrets: ${secrets.join(', ')}`)
  return parts.join(' · ')
}

/** The declared secrets not set on the rrotor, in the warning colour; a reviewer is told how to set them. */
export function missingLine(a: Json, reviewer: boolean): string | null {
  const missing = names(a.secrets_missing)
  if (!missing.length) return null
  const named = `${missing.join(', ')} not set on the rrotor`
  return reviewer ? `${named} · set ${missing.length > 1 ? 'them' : 'it'} with secret_set` : named
}

// /glyphh publish <file> [--name n] [--title t] [--description d] [--type t] [--roles a,b]

type PublishArgs = { path?: string; name?: string; title?: string; description?: string; type?: string; roles: string[] }

/** The command's words: a path, then `--key value` pairs, quotes kept together. */
export function parsePublish(args: string): PublishArgs {
  const unquote = (w: string) => w.replace(/^(["'])(.*)\1$/, '$2')
  const words = args.match(/--\w+=(?:"[^"]*"|'[^']*')|"[^"]*"|'[^']*'|\S+/g)?.map(unquote) ?? []
  const out: PublishArgs = { roles: [] }
  for (let i = 0; i < words.length; i++) {
    const w = words[i]!
    const m = w.match(/^--(name|title|description|type|roles)(?:=(.*))?$/)
    if (!m) {
      if (!out.path) out.path = w
      continue
    }
    const value = m[2] !== undefined ? unquote(m[2]) : (words[++i] ?? '')
    if (m[1] === 'roles') out.roles = value.split(',').map(r => r.trim().toLowerCase()).filter(Boolean)
    else if (m[1] === 'type') out.type = value.trim().toLowerCase()
    else out[m[1] as 'name' | 'title' | 'description'] = value
  }
  return out
}

/** What rrotor takes as an entry, by extension (the spec's 4.1): the type it
 *  implies when none is given, and which go as bytes (base64). */
export const ENTRIES: Record<string, { type: string; binary?: boolean }> = {
  html: { type: 'page' },
  htm: { type: 'page' },
  jsx: { type: 'page' },
  tsx: { type: 'page' },
  md: { type: 'doc' },
  pdf: { type: 'doc', binary: true },
  mmd: { type: 'diagram' },
  mermaid: { type: 'diagram' },
  svg: { type: 'diagram' },
  png: { type: 'design', binary: true },
  jpg: { type: 'design', binary: true },
  jpeg: { type: 'design', binary: true },
  webp: { type: 'design', binary: true },
  gif: { type: 'design', binary: true },
}

/** rrotor's refusal of any other entry, said before rrotor is called. */
export const NOT_AN_ENTRY = 'entry is a page (.html, .jsx, .tsx), a document (.md, .pdf), a diagram (.mmd, .svg) or an image'

export const USAGE_PUBLISH =
  'Usage: /glyphh publish <file> [--name deploy-failures] [--title "Deploy failures"] [--description "..."] [--type dashboard] [--roles sre,admin]'

const EXT = new RegExp(`\\.(${Object.keys(ENTRIES).join('|')})$`, 'i')

/** The name from the file or the title: kebab-case, as rrotor takes it. */
export const slug = (text: string) =>
  text.toLowerCase().replace(EXT, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 63) || 'page'

/** One file from this machine to the local rrotor, as an app awaiting review. */
export async function publishFromCommand(gh: Host, args: string): Promise<string> {
  const given = parsePublish(args)
  if (!given.path) return `Which file? Name what Claude wrote: a page, a document, a diagram or an image.\n${USAGE_PUBLISH}`
  const file = given.path.split('/').pop() ?? given.path
  const ext = file.match(EXT)?.[1]?.toLowerCase() ?? ''
  const kind = ENTRIES[ext]
  if (!kind) return `${given.path}: ${NOT_AN_ENTRY}.\n${USAGE_PUBLISH}`
  if (given.type && !TYPES.some(t => t.id === given.type)) return `${given.type} is not a type: page, dashboard, doc, diagram, deck or design.\n${USAGE_PUBLISH}`
  let text = ''
  let base64 = ''
  try {
    if (kind.binary) base64 = await gh.fs.readBytes(given.path)
    else text = await gh.fs.read(given.path)
  } catch {
    return `Cannot read ${given.path}.`
  }
  const entry = `index.${ext}`
  const type = given.type || kind.type
  const title = given.title?.trim() || text.match(/<title>([^<]+)<\/title>/i)?.[1]?.trim() || text.match(/^#\s+(.+)$/m)?.[1]?.trim() || slug(file)
  const body: AppPublish = {
    name: given.name?.trim() || slug(title),
    title,
    description: given.description?.trim() || `Published from Claude Code: ${file}.`,
    type,
    roles: given.roles,
    files: { [entry]: kind.binary ? { base64 } : text },
    entry,
  }
  try {
    const made = await publishApp(gh, body)
    const me = await loadMe(gh).catch(() => null)
    const who = isReviewer(me) ? 'You review it: /glyphh apps.' : "Awaiting your organisation's admin or reviewer groups."
    const where = made.url ? ` Open: ${made.url}` : ''
    const line = `Published ${body.title} (${str(made.type, type)}) as ${made.program} v${made.version} to your rrotor. ${who}${where}`
    await say(gh, line, false, made.url)
    return line
  } catch (err) {
    const why = describe(err)
    await say(gh, why, true)
    return why
  }
}
