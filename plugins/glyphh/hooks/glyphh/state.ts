import type { AuthState, GlyphhNote, GlyphhSection, Json } from '../../types'
import type { Host } from './host'

export const SECTIONS: { id: GlyphhSection; label: string }[] = [
  { id: 'account', label: 'Account' },
  { id: 'org', label: 'Org' },
  { id: 'plan', label: 'Plan' },
  { id: 'billing', label: 'Billing' },
]

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
