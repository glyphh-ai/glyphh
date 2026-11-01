// The organisation's artifacts (the pages Claude published to its rrotors,
// server/docs/specs/artifacts.md): listed from the catalogue by search, page
// and view; opened at the rrotor; and for a reviewer approved, rejected or
// retired. `/glyphh publish <file>` publishes a page from this machine to the
// local rrotor as an app, awaiting that review.
import type { RenderSurface } from 'claude-code'

import type { ArtifactsView, Json } from '../../types'
import { act, loadMe } from './account'
import { api, describe, listOf } from './api'
import type { Host } from './host'
import { openUrl } from './open'
import { obj, str } from './shape'
import { publishApp, type AppPublish } from './rrotor'
import { say, setList } from './state'

export const PER_PAGE = 24
export const FIRST_VIEW: ArtifactsView = { q: '', page: 1, state: 'approved', total: 0, rejecting: null }

/** The reviewer's views beside the published ones. */
export const VIEWS: { id: string; label: string }[] = [
  { id: 'approved', label: 'Published' },
  { id: 'draft', label: 'Awaiting review' },
  { id: 'rejected', label: 'Rejected' },
]

export const isReviewer = (me: Json | null): boolean => obj(me).reviewer === true

/** The page the view asks for, from `GET /v1/artifacts`: the cards and the count. */
export async function loadArtifacts(gh: Host) {
  const v = await gh.state.artifacts.get()
  const query = new URLSearchParams({ page: String(v.page), per_page: String(PER_PAGE), state: v.state })
  if (v.q) query.set('q', v.q)
  const body = await api<Json>(gh, 'GET', `/v1/artifacts?${query}`)
  await setList(gh, 'artifacts', listOf(body, 'artifacts'))
  const total = typeof body.total === 'number' ? body.total : listOf(body, 'artifacts').length
  await gh.state.artifacts.set(s => ({ ...s, total }))
}

const reload = (gh: Host, change: (v: ArtifactsView) => ArtifactsView) =>
  act(gh, undefined, async () => {
    await gh.state.artifacts.set(change)
    await loadArtifacts(gh)
  })

export const searchArtifacts = (gh: Host, q: string) => reload(gh, v => ({ ...v, q: q.trim(), page: 1 }))

export const turnPage = (gh: Host, by: number) => reload(gh, v => ({ ...v, page: Math.max(1, v.page + by) }))

export const viewArtifacts = (gh: Host, state: string) => reload(gh, v => ({ ...v, state, page: 1, rejecting: null }))

/** The last page's number for the count the server gave. */
export const pages = (v: ArtifactsView) => Math.max(1, Math.ceil(v.total / PER_PAGE))

/** "1–24 of 57": what the page shows of the whole. */
export function pageLine(v: ArtifactsView, shown: number): string {
  if (v.total === 0) return 'Nothing here.'
  const from = (v.page - 1) * PER_PAGE + 1
  return `${from}–${from + shown - 1} of ${v.total}`
}

/** The app in the browser pane on the desktop; the link in a terminal. */
export async function openArtifact(gh: Host, a: Json, surface?: RenderSurface) {
  const url = str(a.url)
  if (!url) return say(gh, 'This artifact has no address yet.', true)
  const opened = await openUrl(gh, url, surface)
  await say(gh, opened ? `${str(a.title)} opened in the browser pane.` : `${str(a.title)}: open this link.`, false, url)
}

const enc = encodeURIComponent

const review = (gh: Host, id: string, verb: string, done: string, body?: Json) =>
  act(gh, done, async () => {
    await api(gh, 'POST', `/v1/artifacts/${enc(id)}/${verb}`, body)
    await gh.state.artifacts.set(v => ({ ...v, rejecting: null }))
    await loadArtifacts(gh)
  })

export const approveArtifact = (gh: Host, id: string) => review(gh, id, 'approve', 'Approved: its people can open it now.')
export const retireArtifact = (gh: Host, id: string) => review(gh, id, 'retire', 'Retired: no longer served or listed.')

/** Reject asks for the reason first: the card shows an input until it is given. */
export const askReason = (gh: Host, id: string | null) => gh.state.artifacts.set(v => ({ ...v, rejecting: id }))

export const rejectArtifact = (gh: Host, id: string, reason: string) => {
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

// /glyphh publish <file> [--name n] [--title t] [--description d] [--roles a,b]

type PublishArgs = { path?: string; name?: string; title?: string; description?: string; roles: string[] }

/** The command's words: a path, then `--key value` pairs, quotes kept together. */
export function parsePublish(args: string): PublishArgs {
  const unquote = (w: string) => w.replace(/^(["'])(.*)\1$/, '$2')
  const words = args.match(/--\w+=(?:"[^"]*"|'[^']*')|"[^"]*"|'[^']*'|\S+/g)?.map(unquote) ?? []
  const out: PublishArgs = { roles: [] }
  for (let i = 0; i < words.length; i++) {
    const w = words[i]!
    const m = w.match(/^--(name|title|description|roles)(?:=(.*))?$/)
    if (!m) {
      if (!out.path) out.path = w
      continue
    }
    const value = m[2] !== undefined ? unquote(m[2]) : (words[++i] ?? '')
    if (m[1] === 'roles') out.roles = value.split(',').map(r => r.trim().toLowerCase()).filter(Boolean)
    else out[m[1] as 'name' | 'title' | 'description'] = value
  }
  return out
}

export const USAGE_PUBLISH = 'Usage: /glyphh publish <page.html|page.md> [--name deploy-failures] [--title "Deploy failures"] [--description "..."] [--roles sre,admin]'

/** The name from the file or the title: kebab-case, as rrotor takes it. */
export const slug = (text: string) =>
  text.toLowerCase().replace(/\.(html?|md)$/, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 63) || 'page'

/** A page from this machine to the local rrotor, as an app awaiting review. */
export async function publishFromCommand(gh: Host, args: string): Promise<string> {
  const given = parsePublish(args)
  if (!given.path) return `Which file? Name the page Claude wrote (an .html or .md file).\n${USAGE_PUBLISH}`
  if (!/\.(html?|md)$/i.test(given.path)) return `${given.path} is not a page: rrotor serves one .html or .md file.\n${USAGE_PUBLISH}`
  let text: string
  try {
    text = await gh.fs.read(given.path)
  } catch {
    return `Cannot read ${given.path}.`
  }
  const file = given.path.split('/').pop() ?? given.path
  const entry = /\.md$/i.test(file) ? 'index.md' : 'index.html'
  const title = given.title?.trim() || text.match(/<title>([^<]+)<\/title>/i)?.[1]?.trim() || text.match(/^#\s+(.+)$/m)?.[1]?.trim() || slug(file)
  const body: AppPublish = {
    name: given.name?.trim() || slug(title),
    title,
    description: given.description?.trim() || `Published from Claude Code: ${file}.`,
    roles: given.roles,
    files: { [entry]: text },
    entry,
  }
  try {
    const made = await publishApp(gh, body)
    const me = await loadMe(gh).catch(() => null)
    const who = isReviewer(me) ? 'You review it: /glyphh artifacts.' : "Awaiting your organisation's admin or reviewer groups."
    const where = made.url ? ` Open: ${made.url}` : ''
    const line = `Published ${body.title} as ${made.program} v${made.version} to your rrotor. ${who}${where}`
    await say(gh, line, false, made.url)
    return line
  } catch (err) {
    const why = describe(err)
    await say(gh, why, true)
    return why
  }
}
