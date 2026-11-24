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

export type GlyphhSection = 'account' | 'org' | 'plan' | 'billing'

/** The panel's last word: what an action did or why not, and a page to open. */
export type GlyphhNote = { text: string; isError: boolean; link?: string }

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
    }
  }
}
