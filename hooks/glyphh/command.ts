// /glyphh [section | signin | signout]: opens the panel there and answers a
// line saying where things stand (in a terminal, the sign-in link too).
import type { GlyphhSection } from '../../types'
import { initAccount, signOut } from './account'
import { openSection } from './actions'
import { openUrl } from './open'
import { watchOpenRequests } from './openreq'
import { resumePolling } from './device'
import type { Host } from './host'
import { beginSignIn } from './sections/signin'
import { planName, str, userOf } from './shape'
import { SECTIONS } from './state'
import { migrateAndLoad } from './wsfiles'

export const ASK_CLAUDE = 'Or ask Claude: "sign in to Glyphh" for a sign-in card in the chat.'

export const USAGE = '/glyphh [signin | signout | account | org | plan | billing | workspaces]'

/** At session start: workspace files (migrated on first run), the sign-in. */
export async function startGlyphh(gh: Host) {
  await migrateAndLoad(gh).catch(() => undefined)
  await initAccount(gh).catch(() => undefined)
  await resumePolling(gh)
  watchOpenRequests(gh)
}

export async function status(gh: Host): Promise<string> {
  const a = await gh.state.auth.get()
  if (a.status === 'pending') {
    const where = a.opened ? ' (open in the browser pane)' : ''
    return `Enter code ${a.user_code} at ${a.verification_uri_complete}${where}. Waiting for approval…`
  }
  if (a.status === 'out') return `Glyphh: signed out${a.error ? ` (${a.error})` : ''}. Sign in: /glyphh signin\n${ASK_CLAUDE}`
  const m = await gh.state.me.get()
  return m ? `Glyphh: signed in as ${str(userOf(m).email)} · ${planName(m)}` : 'Glyphh: signed in.'
}

export async function glyphhCommand(gh: Host, args: string): Promise<{ text: string }> {
  const arg = args.trim().toLowerCase()
  watchOpenRequests(gh)
  const open = args.trim().match(/^open\s+(https?:\/\/\S+\/v1\/device\?code=[A-Z0-9-]+)$/i)
  if (open) {
    // The sign-in card's button: the sign-in page, in the browser pane.
    const url = open[1]!
    return { text: (await openUrl(gh, url)) ? `Opened ${url} in the browser pane. Approve it there.` : `Open ${url} to approve.` }
  }
  // Signed in elsewhere meanwhile (the sign-in card's MCP server writes install.json too)?
  if ((await gh.state.auth.get()).status === 'out') await initAccount(gh, true).catch(() => undefined)
  const placed = await gh.openPanel()
  const signedOut = (await gh.state.auth.get()).status === 'out'
  if (['signin', 'sign-in', 'login'].includes(arg) || (!arg && signedOut)) {
    // Signed out, /glyphh goes straight to sign-in: the code and link land in the panel.
    if ((await gh.state.auth.get()).status !== 'in') await beginSignIn(gh)
  } else if (['signout', 'sign-out', 'logout'].includes(arg)) {
    await signOut(gh)
  } else if (arg && !SECTIONS.some(s => s.id === arg)) {
    return { text: `Usage: ${USAGE}` }
  } else {
    await openSection(gh, (arg || (await gh.state.section.get())) as GlyphhSection)
  }
  await reopen(gh)
  const said = await status(gh)
  const text = signedOut && !said.includes(ASK_CLAUDE) ? `${said}\n${ASK_CLAUDE}` : said
  return { text: placed ? text : `${text}\n(The panel could not be placed here.)` }
}

/** A sign-in still waiting: open its page again in the browser pane. */
async function reopen(gh: Host) {
  const a = await gh.state.auth.get()
  if (a.status !== 'pending') return
  if (await openUrl(gh, a.verification_uri_complete)) {
    await gh.state.auth.set(s => (s.status === 'pending' ? { ...s, opened: true } : s))
  }
}
