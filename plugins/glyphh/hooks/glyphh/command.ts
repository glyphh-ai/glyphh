// /glyphh [section | signin | signout]: opens the panel there and answers a
// line saying where things stand (in a terminal, the sign-in link too).
import type { GlyphhSection } from '../../types'
import { initAccount, signOut } from './account'
import { openSection } from './actions'
import { publishFromCommand } from './apps'
import { linkFromCommand } from './link'
import { openUrl } from './open'
import { resumePolling } from './device'
import type { Host } from './host'
import { beginSignIn } from './sections/signin'
import { planName, str, userOf } from './shape'
import { rrotorShown } from './shelved'
import { shownSections } from './state'

export const ASK_CLAUDE = 'Or ask Claude: "sign in to Glyphh".'

export const USAGE_RROTOR = '/glyphh [login | logout | account | org | plan | billing | apps | publish <file> | link]'
/** rrotor shelved (2026-11-02, ./shelved): no apps, publish or link. */
export const USAGE_SHELVED = '/glyphh [login | logout | account | org | plan | billing]'
export const usage = (rrotor: boolean) => (rrotor ? USAGE_RROTOR : USAGE_SHELVED)

/** At session start: the sign-in. */
export async function startGlyphh(gh: Host) {
  await initAccount(gh).catch(() => undefined)
  await resumePolling(gh)
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
  // Signed in elsewhere meanwhile (another session writes install.json too)?
  if ((await gh.state.auth.get()).status === 'out') await initAccount(gh, true).catch(() => undefined)
  const rrotor = await rrotorShown(gh)
  // /glyphh publish <file>: the file goes to the local rrotor, as an app awaiting review.
  if (rrotor && /^publish(\s|$)/.test(arg)) {
    if ((await gh.state.auth.get()).status !== 'in') return { text: `Sign in to Glyphh first: /glyphh signin\n${ASK_CLAUDE}` }
    return { text: await publishFromCommand(gh, args.trim().replace(/^publish\s*/i, '')) }
  }
  // /glyphh link: this machine's rrotor gets its runtime token from the server and connects out.
  if (rrotor && arg === 'link') {
    if ((await gh.state.auth.get()).status !== 'in') return { text: `Sign in to Glyphh first: /glyphh signin\n${ASK_CLAUDE}` }
    return { text: (await linkFromCommand(gh)).text }
  }
  // /glyphh login and logout stay inline in the chat (their reply row draws the
  // sign-in); only the other sections open the side panel.
  if (['signin', 'sign-in', 'login'].includes(arg)) {
    if ((await gh.state.auth.get()).status !== 'in') await beginSignIn(gh)
    return { text: await status(gh) }
  }
  if (['signout', 'sign-out', 'logout'].includes(arg)) {
    await signOut(gh)
    return { text: 'Signed out of Glyphh.' }
  }
  const placed = await gh.openPanel()
  const signedOut = (await gh.state.auth.get()).status === 'out'
  if (!arg && signedOut) {
    // Signed out, /glyphh goes straight to sign-in: the code and link land in the panel.
    if ((await gh.state.auth.get()).status !== 'in') await beginSignIn(gh)
  } else if (['signout', 'sign-out', 'logout'].includes(arg)) {
    await signOut(gh)
  } else if (arg && !shownSections(rrotor).some(s => s.id === arg)) {
    return { text: `Usage: ${usage(rrotor)}` }
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
