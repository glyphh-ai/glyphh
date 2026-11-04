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

/** A side pane of the desktop app a layout shows (the app's show_pane names). */
export type DipPane = 'diff' | 'file' | 'terminal' | 'pr' | 'tasks' | 'plan' | 'artifact' | 'preview'

/** What fills a cell of a layout's grid: Claude's conversation, a side pane, or '' for nothing. */
export type DipCellPane = DipPane | 'claude' | ''

/** One cell of a grid, stored by its top-left with its spans. */
export type DipCell = { pane: DipCellPane; col: number; row: number; colSpan: number; rowSpan: number }

/** How a layout arranges Claude and its panes: every position of cols × rows covered by exactly one cell. */
export type DipGrid = { cols: number; rows: number; cells: DipCell[] }

/** A terminal tab a layout opens: its title, where its shell starts, the command typed into it ('' for a bare shell). */
export type DipTerminal = { title: string; cwd: string; command: string }

/** A workspace /dip bounces to: the session's folder, the browser tabs (`focus` the one in front, an index into
 *  `tabs`, -1 for none), the grid and the side panes in it (`panes`, in reading order), the terminal tabs, and a
 *  brief Claude reads while it is the active one. */
export type DipLayout = {
  name: string
  folder: string
  tabs: string[]
  focus: number
  grid: DipGrid
  panes: DipPane[]
  terminals: DipTerminal[]
  brief: string
}

/** A layout being written in the Dip pane, its lists as the fields hold them (a URL a line, `*` before the one in
 *  front; `title | cwd | command` a line). `original` is the name it was opened under, null for a new one; `cell`
 *  the grid's selected cell, an index into its cells. */
export type DipDraft = { original: string | null; name: string; folder: string; tabs: string; grid: DipGrid; cell: number; terminals: string; brief: string }

/** The Dip pane: the layouts (kept in the store across sessions), the active one, the draft and the pane's last word. */
export type DipView = { layouts: DipLayout[]; active: string | null; draft: DipDraft | null; note: GlyphhNote | null }

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
      /** /dip: the layouts, the active one, the pane's draft and last word. */
      dip: DipView
    }
  }
}
