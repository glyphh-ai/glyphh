// /glyphh [section | signin | signout]: opens the panel there and answers a
// line saying where things stand (in a terminal, the sign-in link too).
import type { GlyphhSection } from '../../types'
import { initAccount, signOut } from './account'
import { openSection } from './actions'
import { resumePolling } from './device'
import type { Host } from './host'
import { beginSignIn } from './sections/signin'
import { planName, str, userOf } from './shape'
import { SECTIONS } from './state'
import { migrateAndLoad } from './wsfiles'

export const USAGE = '/glyphh [signin | signout | account | org | plan | billing | workspaces]'

/** At session start: workspace files (migrated on first run), the sign-in. */
export async function startGlyphh(gh: Host) {
  await migrateAndLoad(gh).catch(() => undefined)
  await initAccount(gh).catch(() => undefined)
  await resumePolling(gh)
}

export async function status(gh: Host): Promise<string> {
  const a = await gh.state.auth.get()
  if (a.status === 'pending') {
    const where = a.opened ? ' (open in the browser pane)' : ''
    return `Enter code ${a.user_code} at ${a.verification_uri_complete}${where}. Waiting for approval…`
  }
  if (a.status === 'out') return `Glyphh: signed out${a.error ? ` (${a.error})` : ''}. Sign in: /glyphh signin`
  const m = await gh.state.me.get()
  return m ? `Glyphh: signed in as ${str(userOf(m).email)} · ${planName(m)}` : 'Glyphh: signed in.'
}

export async function glyphhCommand(gh: Host, args: string): Promise<{ text: string }> {
  const arg = args.trim().toLowerCase()
  const placed = await gh.openPanel()
  if (['signin', 'sign-in', 'login'].includes(arg)) {
    if ((await gh.state.auth.get()).status !== 'in') await beginSignIn(gh)
  } else if (['signout', 'sign-out', 'logout'].includes(arg)) {
    await signOut(gh)
  } else if (arg && !SECTIONS.some(s => s.id === arg)) {
    return { text: `Usage: ${USAGE}` }
  } else {
    await openSection(gh, (arg || (await gh.state.section.get())) as GlyphhSection)
  }
  const text = await status(gh)
  return { text: placed ? text : `${text}\n(The panel could not be placed here.)` }
}
