import type { AuthState, GlyphhNote, GlyphhSection, Json } from '../../types'
import type { Host } from './host'

export const SECTIONS: { id: GlyphhSection; label: string }[] = [
  { id: 'account', label: 'Account' },
  { id: 'org', label: 'Org' },
  { id: 'plan', label: 'Plan' },
  { id: 'billing', label: 'Billing' },
  { id: 'apps', label: 'Apps' },
]

/** The one section a member of the org has: the admin runs the account, the org, the plan and billing. */
export const MEMBER_SECTION: GlyphhSection = 'apps'

/** The sections a person sees: every one for the org's admin, Apps alone for a member. */
export const sectionsFor = (admin: boolean) => (admin ? SECTIONS : SECTIONS.filter(s => s.id === MEMBER_SECTION))

/** The section a person may open: a member asking for another lands on Apps. */
export const sectionFor = (admin: boolean, id: GlyphhSection): GlyphhSection => (admin ? id : MEMBER_SECTION)

/** The panel's last word. */
export const say = (gh: Host, text: string, isError = false, link?: string) =>
  gh.state.note.set((): GlyphhNote => (link ? { text, isError, link } : { text, isError }))

export const setList = (gh: Host, name: string, items: Json[]) => gh.state.lists.set(all => ({ ...all, [name]: items }))

/** Signed out: everything the server told this session is dropped. */
export async function clearAccount(gh: Host, error?: string) {
  await gh.state.auth.set((): AuthState => (error ? { status: 'out', error } : { status: 'out' }))
  await gh.state.me.set(() => null)
  await gh.state.lists.set(() => ({}))
  await gh.state.inviteLink.set(() => null)
}
