/** The sign-in state the panels draw. The device code stays in session memory. */
export type AuthState =
  | { status: 'out'; error?: string }
  | {
      status: 'pending'
      device_code: string
      user_code: string
      verification_uri: string
      verification_uri_complete: string
      interval: number
      expires_at: number
      opened: boolean
    }
  | { status: 'in'; install_id: string }

export type GlyphhSection = 'account' | 'org' | 'plan' | 'billing' | 'apps'

/** The panel's last word: what an action did or why not, and a page to open. */
export type GlyphhNote = { text: string; isError: boolean; link?: string }

/** The Apps section's place in the catalogue: the search, the page, the view
 *  (a reviewer's `draft` and `rejected` beside `approved`), the type shown
 *  (one of page, dashboard, doc, diagram, deck, design; '' for all), the count
 *  the server gave, and the card whose rejection waits for a reason. */
export type AppsView = { q: string; page: number; state: string; type: string; total: number; rejecting: string | null }

/** A JSON object the server answered, kept as it came. */
export type Json = { [key: string]: unknown }

declare module 'claude-code' {
  interface PluginState {
    glyphh: {
      /** Glyphh account panels: sign-in, the open section, what the server said. */
      auth: AuthState
      section: GlyphhSection
      me: Json | null
      lists: Record<string, Json[]>
      note: GlyphhNote | null
      inviteLink: string | null
      apps: AppsView
    }
  }
}
